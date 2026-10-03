"""Generate the project's original, CC0 PDF fixture (no third-party content)."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "ragglass-field-guide.pdf"
styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=11,
        leading=18,
        spaceAfter=13,
        textColor=colors.HexColor("#34483d"),
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        "Kicker",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        spaceAfter=18,
        textColor=colors.HexColor("#62836a"),
    )
)
styles["Title"].fontName = "Helvetica-Bold"
styles["Title"].fontSize = 25
styles["Title"].leading = 32
styles["Title"].textColor = colors.HexColor("#234733")
styles["Title"].alignment = TA_LEFT
styles["Heading2"].fontSize = 15
styles["Heading2"].textColor = colors.HexColor("#31583c")
story = []


def p(text):
    return Paragraph(text, styles["Body"])


def heading(kicker, title):
    story.extend(
        [
            Paragraph(kicker, styles["Kicker"]),
            Paragraph(title, styles["Title"]),
            Spacer(1, 8 * mm),
        ]
    )


heading("RAGGLASS / ORIGINAL SAMPLE DOCUMENT", "Cedar Pilot<br/>Field Guide")
story.extend(
    [
        p(
            "This is a fictional, self-contained document created for testing RAGGlass. "
            "All Cedar project facts are invented fixture data, "
            "not measurements of a real deployment."
        ),
        Paragraph("1. Pilot overview", styles["Heading2"]),
        p(
            "The Cedar pilot is maintained by Mira Chen. The pilot begins on September 1, 2026 "
            "and ends on September 30, 2026. Its library contains 12 native-text PDF documents."
        ),
        p(
            "The first release accepts PDFs with selectable native text. "
            "Optical character recognition "
            "(OCR) is disabled. Scanned image-only PDFs are outside this release's scope."
        ),
        p(
            "The pilot is intended for engineers inspecting the path from an original "
            "PDF to parsed "
            "content, retrieved evidence, and a grounded answer. The application runs locally."
        ),
        Paragraph("Data ownership", styles["Heading2"]),
        p(
            "Original PDFs and parsed exports are retained on local disk. SQLite stores document "
            "metadata and query history. Qdrant stores the persistent vector index."
        ),
        p(
            "This PDF and its generation script are dedicated to the public domain under CC0 1.0. "
            "You may copy, modify, and redistribute this fixture."
        ),
        PageBreak(),
    ]
)
heading("CEDAR PILOT / CONFIGURATION", "Limits and defaults")
story.extend(
    [
        p(
            "The following table defines the Cedar pilot's configuration. These are fixture "
            "specifications, not benchmark results. Token counts refer to the embedding tokenizer."
        ),
        Paragraph("2. Configuration table", styles["Heading2"]),
    ]
)
rows = [
    ["Setting", "Value", "Meaning"],
    ["Maximum upload size", "30 MB", "Per PDF document"],
    ["Maximum document length", "200 pages", "Per PDF document"],
    ["Chunk window", "240 tokens", "Page-aware token window"],
    ["Chunk overlap", "32 tokens", "Between adjacent windows"],
    ["Retrieved chunks (Top K)", "5", "Maximum chunks per query"],
    ["Minimum cosine score", "0.70", "Retrieval score threshold"],
]
table = Table(rows, colWidths=[68 * mm, 29 * mm, 69 * mm], rowHeights=[12 * mm] * len(rows))
table.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#234733")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f5f1"), colors.white]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6e2d9")),
        ]
    )
)
story.extend(
    [
        KeepTogether([table]),
        Spacer(1, 8 * mm),
        p(
            "For example, one PDF larger than 30 MB must be split or reduced before upload. "
            "The page limit is separate from the file size limit."
        ),
        p(
            "The default retrieval returns at most five chunks; fewer may pass the minimum score. "
            "A cosine similarity score is not a calibrated probability of correctness."
        ),
        PageBreak(),
    ]
)
heading("CEDAR PILOT / EVIDENCE POLICY", "Trace every answer")
story.extend(
    [
        Paragraph("3. Citation contract", styles["Heading2"]),
        p(
            "A model cites retrieved chunk IDs. The backend validates that every cited chunk "
            "belongs to the current query's evidence, then maps it to the original document "
            "and page numbers."
        ),
        p(
            "If the evidence does not answer the question, the answer must say that it cannot be "
            "confirmed from the document. Unsupported sources must not be shown as valid citations."
        ),
        p(
            "A chunk retains its document ID, document SHA-256 hash, chunk ID, page numbers, "
            "parsing settings, and source coordinates when available. "
            "Missing coordinates are explicitly marked."
        ),
        Paragraph("Reproducing a query", styles["Heading2"]),
        p(
            "Every query saves the model name, model HTTP endpoint, prompt, "
            "embedding model revision, chunk settings, retrieval settings, evidence, "
            "validated citations, and measured stage timings."
        ),
        p(
            "After restarting the application, engineers can reopen existing documents "
            "and query history. "
            "The original files, SQLite database, and Qdrant storage must be kept together."
        ),
        Paragraph("Information deliberately omitted", styles["Heading2"]),
        p(
            "This guide does not specify the pilot's annual electricity cost, GPU purchase price, "
            "passwords, or any benchmark latency. Questions about these values cannot be answered "
            "from this document."
        ),
    ]
)


def footer(canvas, doc):
    canvas.setTitle("Cedar Pilot Field Guide — RAGGlass CC0 sample")
    canvas.setAuthor("RAGGlass contributors")
    canvas.setStrokeColor(colors.HexColor("#d6e2d9"))
    canvas.line(22 * mm, 20 * mm, 188 * mm, 20 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#82958a"))
    canvas.drawString(22 * mm, 15 * mm, "RAGGlass · See inside your RAG. · CC0 1.0 fixture")
    canvas.drawRightString(188 * mm, 15 * mm, f"{doc.page} / 3")


if __name__ == "__main__":
    OUTPUT.parent.mkdir(exist_ok=True)
    SimpleDocTemplate(
        str(OUTPUT),
        pagesize=(210 * mm, 297 * mm),
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=24 * mm,
        bottomMargin=28 * mm,
        invariant=1,
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)
