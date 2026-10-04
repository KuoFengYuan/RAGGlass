"""Provider-independent preflight estimates; never confuse E5 tokens with LLM tokens."""

import json

from pydantic import BaseModel, ConfigDict, Field

from .errors import PipelineError


class GenerationOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    max_tokens: int = Field(ge=64, le=4096)

    @classmethod
    def defaults(cls, settings):
        return cls(
            temperature=settings.llm_temperature,
            top_p=settings.llm_top_p,
            max_tokens=settings.llm_max_tokens,
        )


class ContextBudget:
    """UTF-8 bytes plus framing allowance, deliberately labelled as an estimate.

    This is conservative for typical byte-fallback tokenizers. Custom templates,
    hidden reasoning and provider tokenization can differ; native usage is recorded
    separately. No tokenizer/model download or embedding-token shortcut is used.
    """

    def __init__(self, settings, options):
        self.capacity = settings.llm_context_tokens
        self.output = options.max_tokens
        self.margin = settings.llm_context_margin
        self.repair_reserve = 256 if settings.llm_max_repairs else 0

    def measure(self, messages, schema, *, reserve_repair=True):
        serialized = json.dumps(
            {"messages": messages, "schema": schema}, ensure_ascii=False, separators=(",", ":")
        )
        size = len(serialized.encode("utf-8"))
        estimate = size + 128
        repair = self.repair_reserve if reserve_repair else 0
        return {
            "estimator": "utf8-bytes-plus-framing-v1",
            "is_estimate": True,
            "input_characters": len(serialized),
            "input_utf8_bytes": size,
            "estimated_input_tokens": estimate,
            "context_tokens": self.capacity,
            "reserved_output_tokens": self.output,
            "safety_margin_tokens": self.margin,
            "repair_reserve_tokens": repair,
            "input_budget_tokens": self.capacity - self.output - self.margin - repair,
            "fits": estimate + self.output + self.margin + repair <= self.capacity,
        }

    def require(self, messages, schema, *, reserve_repair=False):
        report = self.measure(messages, schema, reserve_repair=reserve_repair)
        if not report["fits"]:
            raise PipelineError(
                "context_budget_exceeded",
                "輸入與輸出保留額度超過 context 預算估算。請縮短問題、降低輸出上限，"
                "或調整模型服務的 context 設定；原始證據已保留。",
                422,
            )
        return report

    def select(self, items, prompt, schema):
        """Keep whole ranked chunks. Every excluded ID remains inspectable in history."""
        selected, omitted = [], []
        for item in items:
            candidate = [*selected, item]
            if self.measure(prompt(candidate), schema)["fits"]:
                selected.append(item)
            else:
                omitted.append(item["id"])
        report = self.measure(prompt(selected), schema)
        report.update(selected_ids=[item["id"] for item in selected], omitted_ids=omitted)
        if items and not selected:
            raise PipelineError(
                "context_budget_exceeded",
                "沒有完整證據片段能放入 context 預算。請縮短問題或降低輸出上限；"
                "不會截斷片段或使用無證據回答。",
                422,
            )
        return selected, report

    def batches(self, items, prompt, schema):
        """Partition all items without dropping a source. A single oversized item fails."""
        batches, batch = [], []
        for item in items:
            if not self.measure(prompt([*batch, item]), schema)["fits"]:
                if batch:
                    batches.append(batch)
                    batch = []
                self.require(prompt([item]), schema, reserve_repair=True)
            batch.append(item)
        if batch:
            batches.append(batch)
        return batches
