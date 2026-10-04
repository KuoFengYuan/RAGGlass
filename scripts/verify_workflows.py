"""Real workflow checks, called inside verify_usability's disposable API/Qdrant workspace."""

import json
import textwrap
import time

from evaluate import evaluate
from reportlab.pdfgen import canvas


def complaint_pdf(path):
    """Generate a fictional CC0 native-text complaint, never an uploaded private document."""
    pages = [
        "Nora Lin bought a Cedar storage appliance, order CL-204, on 2026-09-18 for NTD 12800. "
        "The appliance stopped working after two days. This complaint requests a resolution.",
        "The reported failure is that the appliance cannot start and the indicator remains red. "
        "The customer followed the published restart instructions without restoring operation.",
        "Support promised a replacement by 2026-09-25. The replacement never arrived. "
        "There was no shipment confirmation or tracking number after the promised date.",
        "Nora sent two follow-up emails on 2026-09-26 and 2026-09-29. "
        "Neither email received a substantive response explaining the missed replacement.",
        "The customer now requests a full refund of NTD 12800 by 2026-10-08. "
        "The preferred solution is a refund rather than another replacement promise.",
        "Support must provide a prepaid return label and a written refund status update. "
        "The next action is to acknowledge the complaint and confirm the refund timeline.",
    ]
    pdf = canvas.Canvas(str(path), pagesize=(612, 792), invariant=1)
    pdf.setTitle("Fictional CC0 support complaint")
    for number, core in enumerate(pages, 1):
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(42, 747, f"Fictional CC0 complaint - section {number}")
        text = pdf.beginText(42, 716)
        text.setFont("Helvetica", 10)
        text.setLeading(14)
        # Extra narrative makes the whole document exceed one model-input estimate.
        for paragraph in range(8):
            content = core + (
                f" Detail record {number}.{paragraph + 1}: this section describes the same "
                "support incident. The customer needs an accurate written explanation and a "
                "clear action from the support team. All names and events are fictional."
            )
            for line in textwrap.wrap(content, width=98):
                text.textLine(line)
            text.textLine("")
        pdf.drawText(text)
        pdf.showPage()
    pdf.save()


def check_workflows(client, doc, report, checked, root, directory, wait_run):
    workflow_report = {}
    report["workflows"] = workflow_report
    request = {"document_ids": [doc["id"]], "top_k": 5, "score_threshold": 0.7}
    options = {"temperature": 0.2, "top_p": 0.9, "max_tokens": 512}
    response = client.post(
        "query",
        json={
            **request,
            "question": "What is the maximum upload size for the Cedar pilot?",
            "generation": options,
        },
    )
    response.raise_for_status()
    run = response.json()
    assert run["status"] == "completed" and "30 MB" in run["answer"]
    assert all(run["settings"]["llm"][key] == value for key, value in options.items())
    assert run["usage"]["reported_calls"] >= 1
    assert run["attempts"][0]["context"]["actual_input_tokens"] > 0
    assert run["context"]["is_estimate"] and run["context"]["fits"]
    workflow_report["generation_options"] = run
    checked(
        "live per-run Temperature/Top-P/output limit and separate estimated/native token counts"
    )

    response = client.post(
        "query",
        json={
            **request,
            "top_k": 12,
            "score_threshold": 0,
            "question": "What is the maximum upload size for the Cedar pilot?\n"
            + "請依據文件回答。" * 120,
        },
    )
    response.raise_for_status()
    bounded = response.json()
    assert bounded["status"] == "completed", bounded.get("error")
    assert bounded["context"]["omitted_ids"] and bounded["context"]["selected_ids"]
    assert all(c["id"] in bounded["context"]["selected_ids"] for c in bounded["citations"])
    assert set(bounded["context"]["selected_ids"] + bounded["context"]["omitted_ids"]) == {
        e["id"] for e in bounded["evidence"]
    }
    workflow_report["context_selection"] = bounded
    checked("live whole-chunk context selection retains excluded evidence and restricts citations")

    fixture = directory / "fictional-complaint.pdf"
    complaint_pdf(fixture)
    with fixture.open("rb") as file:
        response = client.post("documents", files={"file": (fixture.name, file, "application/pdf")})
    response.raise_for_status()
    complaint = response.json()
    deadline = time.monotonic() + 600
    while complaint["status"] not in {"ready", "failed"}:
        if time.monotonic() > deadline:
            raise TimeoutError("Complaint parsing exceeded 600 seconds")
        time.sleep(0.2)
        complaint = client.get(f"documents/{complaint['id']}").json()
    assert complaint["status"] == "ready", complaint.get("error")
    workflow_report["complaint_document"] = complaint
    checked(f"real fictional complaint parsing/indexing: {complaint['chunk_count']} chunks")
    response = client.post(
        "summary/start", json={"document_ids": [complaint["id"]], "language": "en"}
    )
    response.raise_for_status()
    summary, stages = wait_run(client, response.json()["id"])
    workflow_report["summary"] = {"run": summary, "observed_stages": stages}
    print(
        f"SUMMARY status={summary['status']} points={len(summary.get('summary_points', []))} "
        f"map_batches={summary.get('workflow', {}).get('map_batches')} "
        f"source_characters={sum(len(c['text']) for c in summary['evidence'])}",
        flush=True,
    )
    assert summary["status"] == "completed", summary.get("error")
    assert len(summary["summary_points"]) == 3 and summary["workflow"]["map_batches"] > 1
    assert len(summary["workflow"]["mapped_source_ids"]) == complaint["chunk_count"]
    normalized = summary["answer"].replace(",", "")
    assert "12800" in normalized and "2026-10-08" in normalized and "refund" in normalized.lower()
    assert all(c["id"] in {e["id"] for e in summary["evidence"]} for c in summary["citations"])
    assert summary["usage"]["reported_calls"] == len(summary["attempts"])
    checked(f"live multi-step three-point complaint summary: {summary['timings_ms']['total']} ms")

    response = client.post(
        "summary/start", json={"document_ids": [complaint["id"]], "language": "en"}
    )
    response.raise_for_status()
    rid = response.json()["id"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        pending = client.get(f"runs/{rid}").json()
        if (
            len(pending.get("workflow", {}).get("nodes", [])) >= 2
            and pending["stage"] == "generation"
        ):
            break
        assert pending["status"] == "running", pending.get("error")
        time.sleep(0.01)
    else:
        raise TimeoutError("Summary did not reach its second node")
    client.post(f"runs/{rid}/cancel").raise_for_status()
    stopped, _ = wait_run(client, rid)
    assert stopped["status"] == "cancelled" and not stopped["answer"]
    assert stopped["workflow"]["nodes"][0]["status"] == "completed"
    assert stopped["workflow"]["nodes"][-1]["status"] == "cancelled"
    workflow_report["cancelled_summary"] = stopped
    checked("real summary cancellation keeps completed notes and prevents a final answer")

    dataset = json.loads((root / "examples/evaluation-cases.json").read_text())
    evaluation = evaluate(client, doc["id"], dataset)
    assert evaluation["metrics"]["completed"] == len(dataset["cases"])
    (root / ".data/workflows-evaluation.json").write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n"
    )
    workflow_report["evaluation"] = {
        "metrics": evaluation["metrics"],
        "provenance": evaluation["provenance"],
    }
    checked(
        "measured bilingual evaluation; page recall and literal fact checks reported separately"
    )


if __name__ == "__main__":
    from verify_usability import main

    main(browser=True, workflows=True)
