from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from ragglass.config import Settings
from ragglass.main import create_app
from ragglass.uploads import inspect_pdf


def test_invalid_and_encrypted_uploads_are_actionable(tmp_path):
    app = create_app(Settings(ragglass_data_dir=tmp_path))
    with TestClient(app) as client:
        invalid = client.post("/api/documents", files={"file": ("not.pdf", b"not a PDF")})
        assert invalid.status_code == 422
        assert "PDF" in invalid.json()["detail"]
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.encrypt("fixture-password")
        buffer = BytesIO()
        writer.write(buffer)
        encrypted = client.post("/api/documents", files={"file": ("locked.pdf", buffer.getvalue())})
        assert encrypted.status_code == 422
        assert "密碼" in encrypted.json()["detail"]
        assert client.get("/api/documents").json() == []


def test_missing_documents_and_empty_questions_are_rejected(tmp_path):
    app = create_app(Settings(ragglass_data_dir=tmp_path))
    with TestClient(app) as client:
        assert client.get("/api/documents/unknown/pdf").status_code == 404
        response = client.post("/api/query", json={"question": "", "document_ids": ["unknown"]})
        assert response.status_code == 422


def test_upload_preflight_enforces_size_pages_and_native_text_before_queueing(tmp_path):
    app = create_app(Settings(ragglass_data_dir=tmp_path, max_upload_mb=1, max_pdf_pages=2))
    with TestClient(app) as client:
        config = client.get("/api/config").json()
        assert config["max_upload_mb"] == 1 and config["max_pdf_pages"] == 2
        large = client.post(
            "/api/documents", files={"file": ("large.pdf", b"%PDF-" + b"0" * 1024**2)}
        )
        assert large.status_code == 413
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buffer = BytesIO()
        writer.write(buffer)
        blank = client.post("/api/documents", files={"file": ("blank.pdf", buffer.getvalue())})
        assert blank.status_code == 422 and "OCR" in blank.json()["detail"]
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)
        buffer = BytesIO()
        writer.write(buffer)
        pages = client.post("/api/documents", files={"file": ("pages.pdf", buffer.getvalue())})
        assert pages.status_code == 422 and "頁數" in pages.json()["detail"]
        assert client.get("/api/documents").json() == []
        assert not app.state.ingest_jobs.active
        assert list((tmp_path / "documents").iterdir()) == []


def test_native_text_on_later_page_passes_preflight():
    # Real bytes from the public fictional sample; no parser/model inference in this contract.
    from pathlib import Path

    sample = Path(__file__).resolve().parents[1] / "examples/ragglass-field-guide.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_page(PdfReader(sample).pages[0])
    buffer = BytesIO()
    writer.write(buffer)
    assert inspect_pdf(buffer.getvalue(), Settings()) == 2
