"""Generate an original, fictional CC0 retrieval PDF and its bilingual annotations."""

import hashlib
import json
import textwrap
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import CIDEncoding, UnicodeCIDFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    (
        "CEDAR-X17 service record",
        "Model CEDAR-X17 runs firmware FW-7.2-A. Error E-4097 means cache checksum mismatch. "
        "The documented retry delay is 180 milliseconds. Storage capacity is 256 GB. "
        "These values belong only to CEDAR-X17, not CEDAR-X71 or CEDAR-X17-R. "
        "Support must check the exact model and error identifier before applying a procedure. "
        "This is invented test data, not a real product specification.",
    ),
    (
        "CEDAR-X71 service record",
        "Model CEDAR-X71 runs firmware FW-7.2-B. Error E-4079 means controller temperature "
        "above the safety limit. The documented retry delay is 810 milliseconds. Storage "
        "capacity is 512 GB. These values belong only to CEDAR-X71, not CEDAR-X17 or "
        "CEDAR-X17-R. Support must check the exact model and error identifier before applying "
        "a procedure. This is invented test data, not a real product specification.",
    ),
    (
        "CEDAR-X17-R service record",
        "Model CEDAR-X17-R runs firmware FW-7.2-R. Error E-4097R means mirror synchronization "
        "incomplete. The documented retry delay is 360 milliseconds. Storage capacity is 1024 "
        "GB. This replacement revision is distinct from CEDAR-X17 and CEDAR-X71. Support "
        "must check the exact model and error identifier before applying a procedure. "
        "This is invented test data, not a real product specification.",
    ),
    (
        "Order CDR-2026-017",
        "Order CDR-2026-017 has a total amount of NTD 12800 and a delivery deadline of "
        "2026-10-08. The buyer is Nora Lin. The delivery address is omitted. "
        "This order is independent of order CDR-2026-071. Their amounts and deadlines "
        "must not be interchanged. This is an invented order for retrieval testing.",
    ),
    (
        "Order CDR-2026-071",
        "Order CDR-2026-071 has a total amount of NTD 18200 and a delivery deadline of "
        "2026-10-18. The buyer is Ivan Wu. The delivery address is omitted. "
        "This order is independent of order CDR-2026-017. Their amounts and deadlines "
        "must not be interchanged. This is an invented order for retrieval testing.",
    ),
    (
        "中文文件庫政策",
        "文件庫保留查詢紀錄九十天。使用者可以匯出自己的紀錄。刪除文件後，歷史答案與引用文字仍會保留，"
        "但原始 PDF 的頁面連結會停用。刪除查詢紀錄不會刪除文件。文件庫不儲存信用卡號碼。"
        "這些規則僅供虛構的測試文件使用。",
    ),
    (
        "Faulty equipment exchange policy",
        "A malfunctioning unit is exchanged for a working unit at no charge within fourteen "
        "calendar days after the support team receives it. The customer must describe the "
        "fault and provide the model identifier. This exchange policy applies to broken "
        "equipment. It is separate from the unopened-product return policy. "
        "The replacement shipping cost is paid by the support team.",
    ),
    (
        "Unopened equipment return policy",
        "An unopened, unwanted unit may be returned for credit within seven calendar days "
        "after delivery. The customer pays return shipping. This policy applies only to "
        "unopened products and must not be used for malfunctioning equipment. "
        "No annual electricity cost, administrator password, or spare-part price is given "
        "anywhere in this fictional retrieval lab.",
    ),
]
# English / Traditional Chinese paired cases: exact IDs, numbers, similar records,
# paraphrases, and absent facts. Page-level labels are not claim-level entailment labels.
CASES = [
    (
        "identifier",
        "What does error E-4097 mean for CEDAR-X17?",
        "CEDAR-X17 的 E-4097 是什麼錯誤？",
        1,
        ["checksum", "校驗", "檢查碼", "檢查和"],
    ),
    (
        "identifier",
        "Which firmware does CEDAR-X71 run?",
        "CEDAR-X71 使用哪個韌體版本？",
        2,
        ["FW-7.2-B"],
    ),
    (
        "numeric",
        "What is the retry delay for CEDAR-X17 in milliseconds?",
        "CEDAR-X17 的重試延遲是多少毫秒？",
        1,
        ["180"],
    ),
    (
        "numeric",
        "What is the delivery deadline for order CDR-2026-017?",
        "訂單 CDR-2026-017 的交貨截止日期是哪天？",
        4,
        ["2026-10-08", "October 8", "10 月 8", "10月8"],
    ),
    (
        "similar-records",
        "What amount is due for CDR-2026-071, rather than CDR-2026-017?",
        "CDR-2026-071 的金額是多少？請勿混用 CDR-2026-017 的金額。",
        5,
        ["18200", "18,200"],
    ),
    (
        "similar-records",
        "How many days are query records kept in the document library?",
        "文件庫會保留查詢紀錄幾天？",
        6,
        ["90", "ninety", "九十"],
    ),
    (
        "paraphrase",
        "How long does a free replacement of broken equipment take after support receives it?",
        "客服收到故障設備後，免費換新要等多久？",
        7,
        ["fourteen", "14", "十四"],
    ),
    (
        "unanswerable",
        "What is the administrator password for CEDAR-X17?",
        "CEDAR-X17 的管理員密碼是什麼？",
        None,
        [],
    ),
]


def generate(output, annotations):
    font = UnicodeCIDFont("MSung-Light")
    # ReportLab 4.4.4 defaults MSung's CNS1 font to the GB1 CMap. Explicitly use
    # the matching CNS Unicode map so visible glyphs, PDF.js and source text agree.
    font.encodingName = "UniCNS-UCS2-H"
    font.encoding = CIDEncoding(font.encodingName)
    pdfmetrics.registerFont(font)
    pdf = canvas.Canvas(str(output), pagesize=(612, 792), invariant=1)
    pdf.setTitle("RAGGlass retrieval lab - fictional CC0 fixture")
    pdf.setAuthor("RAGGlass contributors")
    for page, (title, content) in enumerate(PAGES, 1):
        font = "MSung-Light" if page == 6 else "Helvetica"
        pdf.setFont(font, 15)
        pdf.drawString(42, 742, title)
        text = pdf.beginText(42, 697)
        text.setFont(font, 12)
        text.setLeading(21)
        for line in textwrap.wrap(content, width=36 if page == 6 else 78):
            text.textLine(line)
        pdf.drawText(text)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(
            42, 42, f"Fictional CC0 test data - RAGGlass retrieval lab - page {page} / 8"
        )
        pdf.showPage()
    pdf.save()
    cases = []
    for number, (category, en, zh, page, variants) in enumerate(CASES, 1):
        for language, question in (("en", en), ("zh", zh)):
            cases.append(
                {
                    "id": f"{language}-{number}",
                    "category": category,
                    "question": question,
                    "answerable": page is not None,
                    "expected_pages": [page] if page else [],
                    "expected_any": variants,
                }
            )
    annotations.write_text(
        json.dumps(
            {
                "version": "retrieval-lab-bilingual-v1",
                "license": "CC0-1.0; fictional fixture and annotations",
                "document_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "cases": cases,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    output = ROOT / "examples/ragglass-retrieval-lab.pdf"
    generate(output, ROOT / "examples/retrieval-cases.json")
    print(output)
