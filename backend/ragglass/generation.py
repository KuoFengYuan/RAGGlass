"""Bounded model calls with validation feedback, persistence and cooperative cancellation."""

import asyncio
import random
import time

from .context import ContextBudget, GenerationOptions
from .errors import PipelineError
from .store import now

REPAIR_CODES = {"invalid_model_response", "invalid_citation"}


def native_usage(metrics):
    usage = metrics.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    values = (
        metrics.get("prompt_eval_count", usage.get("prompt_tokens")),
        metrics.get("eval_count", usage.get("completion_tokens")),
    )
    return tuple(value if type(value) is int and value >= 0 else None for value in values)


class GenerationRunner:
    def __init__(self, settings, client, run, save, control):
        self.settings, self.client, self.run = settings, client, run
        self.save, self.control = save, control
        self.options = GenerationOptions.model_validate(
            {key: run["settings"]["llm"][key] for key in GenerationOptions.model_fields}
        )
        self.budget = ContextBudget(settings, self.options)
        self.deadline = time.monotonic() + settings.workflow_timeout_seconds
        run["attempts"] = []
        run["usage"] = {
            "reported_input_tokens": 0,
            "reported_output_tokens": 0,
            "reported_calls": 0,
            "unreported_calls": 0,
        }

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise PipelineError("workflow_timeout", "工作流程已達時間上限，請縮小文件或重試。", 504)
        return remaining

    async def complete(self, messages, schema, validate, *, node="answer"):
        original = messages
        repairs = 0
        reason = "initial"
        for number in range(1, self.settings.llm_max_attempts + 1):
            self.control.check()
            remaining = self.remaining()
            if len(self.run["attempts"]) >= self.settings.workflow_max_calls:
                raise PipelineError(
                    "workflow_call_limit", "工作流程已達模型呼叫上限，請縮小文件後重試。", 422
                )
            report = self.budget.require(messages, schema)
            attempt = {
                "node": node,
                "number": number,
                "reason": reason,
                "status": "running",
                "started_at": now(),
                "prompt": messages,
                "context": report,
            }
            self.run["attempts"].append(attempt)
            self.run.update(stage="generation", stage_started_at=now(), prompt=messages)
            self.save(self.run)
            started = time.perf_counter()
            try:
                # The outer stage owns this task. Stop cancels calls and backoff sleeps alike.
                async with asyncio.timeout(remaining):
                    raw, metrics = await self.client.generate_async(
                        messages,
                        options=self.options,
                        schema=schema,
                        timeout=min(remaining, self.settings.llm_timeout_seconds),
                    )
                attempt.update(raw_response=raw, model_metrics=metrics)
                self.run.update(raw_response=raw, model_metrics=metrics)
                input_tokens, output_tokens = native_usage(metrics)
                if input_tokens is not None:
                    self.run["usage"]["reported_input_tokens"] += input_tokens
                    attempt["context"]["actual_input_tokens"] = input_tokens
                    attempt["context"]["actual_exceeds_reservation"] = (
                        input_tokens + self.options.max_tokens + self.budget.margin
                        > self.budget.capacity
                    )
                if output_tokens is not None:
                    self.run["usage"]["reported_output_tokens"] += output_tokens
                    attempt["context"]["actual_output_tokens"] = output_tokens
                if input_tokens is not None and output_tokens is not None:
                    self.run["usage"]["reported_calls"] += 1
                self.control.check()
                self.run.update(stage="citation_validation", stage_started_at=now())
                self.save(self.run)
                validation_started = time.perf_counter()
                try:
                    result = validate(raw)
                finally:
                    attempt["validation_ms"] = round(
                        (time.perf_counter() - validation_started) * 1000, 2
                    )
                    timings = self.run["timings_ms"]
                    timings["citation_validation"] = round(
                        timings.get("citation_validation", 0) + attempt["validation_ms"], 2
                    )
                attempt["status"] = "completed"
                return result
            except TimeoutError as exc:
                attempt.update(status="failed", error_code="workflow_timeout")
                raise PipelineError(
                    "workflow_timeout", "工作流程已達時間上限，請縮小文件或重試。", 504
                ) from exc
            except asyncio.CancelledError:
                attempt["status"] = "cancelled"
                raise
            except PipelineError as exc:
                attempt.update(status="failed", error_code=exc.code, error=exc.message)
                if number == self.settings.llm_max_attempts:
                    raise
                if exc.code in REPAIR_CODES and repairs < self.settings.llm_max_repairs:
                    repairs += 1
                    reason = "validation_repair"
                    # Never append untrusted invalid output or foreign IDs to the next prompt.
                    messages = [
                        *original,
                        {
                            "role": "user",
                            "content": "Validation error: "
                            + exc.code
                            + ". Return the required JSON schema with only source IDs from this "
                            "request. Refuse unsupported claims.",
                        },
                    ]
                elif exc.retryable:
                    reason = "transport_retry"
                    delay = min(
                        self.settings.llm_retry_delay_seconds
                        * 2 ** (number - 1)
                        * random.uniform(0.8, 1.2),
                        self.remaining(),
                    )
                    attempt["backoff_seconds"] = round(delay, 3)
                    self.run.update(stage="retry_wait", stage_started_at=now())
                    self.save(self.run)
                    await asyncio.sleep(delay)
                else:
                    raise
            except BaseException:
                attempt["status"] = "cancelled" if self.control.cancelled else "failed"
                raise
            finally:
                if not {"actual_input_tokens", "actual_output_tokens"} <= attempt["context"].keys():
                    self.run["usage"]["unreported_calls"] += 1
                attempt.update(
                    finished_at=now(), elapsed_ms=round((time.perf_counter() - started) * 1000, 2)
                )
                self.save(self.run)
