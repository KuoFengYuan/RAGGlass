import importlib.metadata
import threading
import uuid
from collections import defaultdict
from pathlib import Path

from .config import Settings
from .errors import PipelineError


class Parser:
    """Docling native-text PDF adapter; preserve full provenance without inventing boxes."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._converter = None
        self._lock = threading.Lock()

    def snapshot(self):
        return {
            "engine": "docling",
            "version": importlib.metadata.version("docling"),
            "ocr": False,
            "table_structure": True,
            "table_mode": "accurate",
            "device": "cpu",
            "cpu_threads": self.settings.cpu_threads,
            "max_pages": self.settings.max_pdf_pages,
        }

    def parse(self, path: Path):
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            AcceleratorDevice,
            AcceleratorOptions,
            PdfPipelineOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling_core.types.doc import TableItem

        with self._lock:
            if self._converter is None:
                options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
                options.accelerator_options = AcceleratorOptions(
                    device=AcceleratorDevice.CPU, num_threads=self.settings.cpu_threads
                )
                self._converter = DocumentConverter(
                    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
                )
            result = self._converter.convert(path, max_num_pages=self.settings.max_pdf_pages)
            if result.status.value != "success":
                raise PipelineError("parse_failed", "Docling 解析未完整成功，請檢查 PDF。", 422)
            doc = result.document
            groups = defaultdict(list)
            for item, _ in doc.iterate_items():
                if isinstance(item, TableItem):
                    text = item.export_to_markdown(doc=doc)
                else:
                    text = getattr(item, "text", "")
                if not text or not text.strip():
                    continue
                provenance = []
                for p in getattr(item, "prov", []):
                    page = p.page_no
                    size = doc.pages[page].size
                    provenance.append(
                        {
                            "page": page,
                            "bbox": p.bbox.model_dump(mode="json") if p.bbox else None,
                            "page_width": size.width,
                            "page_height": size.height,
                            "item_ref": item.self_ref,
                        }
                    )
                pages = sorted({p["page"] for p in provenance})
                if not pages:
                    # No source page means no usable RAG citation; keep it in raw export only.
                    continue
                groups[tuple(pages)].append(
                    {"text": text.strip(), "provenance": provenance, "label": str(item.label)}
                )
            if not groups:
                raise PipelineError(
                    "no_native_text",
                    "找不到可引用的原生文字。本里程碑不含 OCR，請使用可選取文字的 PDF。",
                    422,
                )
            return {
                "page_count": len(doc.pages),
                "groups": [(list(pages), items) for pages, items in sorted(groups.items())],
                "docling": doc.export_to_dict(),
                "markdown": doc.export_to_markdown(),
            }


def make_chunks(parsed, document, tokenizer, size, overlap):
    """Page-aware token windows. Multi-page items retain every source page/box."""
    chunks = []
    for pages, items in parsed["groups"]:
        # Tokenize the final joined text, so model input never silently truncates a chunk.
        text = "\n\n".join(item["text"] for item in items)
        encoding = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        offsets = encoding["offset_mapping"]
        item_ranges = []
        cursor = 0
        for item in items:
            item_ranges.append((cursor, cursor + len(item["text"]), item))
            cursor += len(item["text"]) + 2
        start = 0
        while start < len(offsets):
            stop = min(start + size, len(offsets))
            left, right = offsets[start][0], offsets[stop - 1][1]
            chunk_text = text[left:right].strip()
            sources = []
            for a, b, item in item_ranges:
                if a < right and b > left:
                    sources.extend(item["provenance"])
            cid = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"{document['id']}:{len(chunks)}:{chunk_text}")
            )
            chunks.append(
                {
                    "id": cid,
                    "document_id": document["id"],
                    "document_hash": document["hash"],
                    "filename": document["filename"],
                    "page": pages[0],
                    "pages": pages,
                    "text": chunk_text,
                    "token_count": stop - start,
                    "provenance": sources,
                    "coordinates_available": any(p["bbox"] for p in sources),
                    "coordinate_scope": "source_item" if sources else "unavailable",
                }
            )
            if stop == len(offsets):
                break
            start = stop - overlap
    return chunks
