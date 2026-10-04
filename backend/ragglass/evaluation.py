"""Small annotated smoke evaluations, with explicit limits on what scores establish."""

import math
import statistics


def score_case(case, run):
    completed = run["status"] == "completed"
    gold = set(case.get("expected_pages", []))
    retrieved = {page for item in run["evidence"] for page in item["pages"]}
    cited = {page for item in run["citations"] for page in item["pages"]}
    text = (run.get("answer") or "").casefold()
    variants = case.get("expected_any", [])
    return {
        "id": case["id"],
        "run_id": run["id"],
        "status": run["status"],
        "expected_answerable": case["answerable"],
        "answerable": run["answerable"],
        "answerability_match": completed and run["answerable"] == case["answerable"],
        "gold_page_recall_at_k": len(gold & retrieved) / len(gold) if gold else None,
        "gold_page_citation_coverage": len(gold & cited) / len(gold) if gold else None,
        "expected_text_match": any(v.casefold() in text for v in variants) if variants else None,
        "latency_ms": run["timings_ms"]["total"],
        "usage": run.get("usage"),
    }


def aggregate(scores):
    def mean(key):
        values = [s[key] for s in scores if s[key] is not None]
        return round(statistics.mean(values), 4) if values else None

    timings = sorted(s["latency_ms"] for s in scores)
    return {
        "cases": len(scores),
        "completed": sum(s["status"] == "completed" for s in scores),
        "answerability_matches": sum(s["answerability_match"] for s in scores),
        "gold_page_recall_at_k_mean": mean("gold_page_recall_at_k"),
        "gold_page_citation_coverage_mean": mean("gold_page_citation_coverage"),
        "expected_text_match_rate": mean("expected_text_match"),
        "unanswerable_refused": sum(
            not s["expected_answerable"] and not s["answerable"] and s["status"] == "completed"
            for s in scores
        ),
        "answerable_refused": sum(
            s["expected_answerable"] and not s["answerable"] and s["status"] == "completed"
            for s in scores
        ),
        "latency_median_ms": round(statistics.median(timings), 2) if timings else None,
        "latency_p95_ms": timings[math.ceil(len(timings) * 0.95) - 1] if timings else None,
        "reported_input_tokens": sum(
            (s.get("usage") or {}).get("reported_input_tokens", 0) for s in scores
        ),
        "reported_output_tokens": sum(
            (s.get("usage") or {}).get("reported_output_tokens", 0) for s in scores
        ),
        "calls_with_unknown_usage": sum(
            (s.get("usage") or {}).get("unreported_calls", 0) for s in scores
        ),
    }


def comparison(previous, current):
    if previous["provenance"] != current["provenance"]:
        return {
            "comparable": False,
            "reason": "Dataset, document or retrieval/index settings differ",
        }
    return {
        "comparable": True,
        "previous_generation": previous["generation"],
        "current_generation": current["generation"],
        "deltas": {
            key: round(value - previous["metrics"][key], 4)
            for key, value in current["metrics"].items()
            if value is not None and previous["metrics"].get(key) is not None
        },
    }
