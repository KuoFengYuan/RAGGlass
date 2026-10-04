"""Validate before reserving a document or invoking Docling/embedding models."""

from io import BytesIO

from fastapi import HTTPException
from pypdf import PdfReader


def inspect_pdf(data, settings):
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"PDF 超過 {settings.max_upload_mb} MB，請縮小或拆分檔案。")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(422, "檔案不是有效的 PDF，請上傳 PDF 文件。")
    try:
        pdf = PdfReader(BytesIO(data))
        if pdf.is_encrypted:
            raise HTTPException(422, "PDF 已加密，請先移除密碼後上傳。")
        count = len(pdf.pages)
        if not 1 <= count <= settings.max_pdf_pages:
            raise HTTPException(422, f"PDF 頁數須介於 1 與 {settings.max_pdf_pages}，請拆分文件。")
        if not any((page.extract_text() or "").strip() for page in pdf.pages):
            raise HTTPException(
                422, "PDF 沒有可選取文字，可能是掃描圖片。目前不支援 OCR，請使用含文字的 PDF。"
            )
        return count
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "PDF 損壞或無法讀取，請重新匯出 PDF。") from exc
