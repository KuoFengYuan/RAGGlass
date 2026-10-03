from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from ragglass.config import Settings
from ragglass.main import create_app


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
