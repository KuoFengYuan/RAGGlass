import hashlib
import json
import threading

from qdrant_client import QdrantClient, models

from .errors import PipelineError


class VectorIndex:
    """Qdrant adapter; model/revision fingerprint prevents mixed embedding spaces."""

    def __init__(self, settings, embedder):
        self.client = QdrantClient(
            url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=20
        )
        fingerprint = hashlib.sha256(
            json.dumps(embedder.snapshot(), sort_keys=True).encode()
        ).hexdigest()[:16]
        self.collection = f"ragglass_{fingerprint}"
        self._lock = threading.Lock()

    def begin_document(self, doc_id, dimension):
        """Prepare once per full reindex; successive batch writes never delete earlier batches."""
        try:
            with self._lock:
                if not self.client.collection_exists(self.collection):
                    self.client.create_collection(
                        self.collection,
                        vectors_config=models.VectorParams(
                            size=dimension, distance=models.Distance.COSINE
                        ),
                    )
                    self.client.create_payload_index(
                        self.collection, "document_id", models.PayloadSchemaType.KEYWORD
                    )
                # Re-index is idempotent and removes obsolete chunks from this document.
                self.client.delete(
                    self.collection,
                    models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="document_id",
                                    match=models.MatchValue(value=doc_id),
                                )
                            ]
                        )
                    ),
                    wait=True,
                )
        except Exception as exc:
            raise self._write_error() from exc

    def upsert_batch(self, chunks, vectors):
        try:
            with self._lock:
                self.client.upsert(
                    self.collection,
                    points=[
                        models.PointStruct(id=c["id"], vector=v, payload=c)
                        for c, v in zip(chunks, vectors, strict=True)
                    ],
                    wait=True,
                )
        except Exception as exc:
            raise self._write_error() from exc

    def index(self, chunks, vectors):
        # Compatibility helper; ingestion uses begin_document + bounded upsert_batch.
        self.begin_document(chunks[0]["document_id"], len(vectors[0]))
        for start in range(0, len(chunks), 64):
            self.upsert_batch(chunks[start : start + 64], vectors[start : start + 64])

    @staticmethod
    def _write_error():
        return PipelineError(
            "qdrant_unavailable",
            "無法寫入 Qdrant。請執行 docker compose up -d qdrant，確認 QDRANT_URL 後重新索引。",
        )

    def search(self, vector, document_ids, top_k, threshold):
        try:
            points = self.client.query_points(
                self.collection,
                query=vector,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchAny(any=document_ids)
                        )
                    ]
                ),
                limit=top_k,
                score_threshold=threshold,
                with_payload=True,
            ).points
            return [{**p.payload, "score": p.score, "rank": n + 1} for n, p in enumerate(points)]
        except Exception as exc:
            raise PipelineError(
                "qdrant_unavailable",
                "無法查詢 Qdrant。請確認容器運行、QDRANT_URL，以及文件已完成索引。",
            ) from exc

    def delete_document(self, document_id):
        """Remove this ID from every RAGGlass embedding space, including old revisions."""
        try:
            with self._lock:
                for collection in self.client.get_collections().collections:
                    if not collection.name.startswith("ragglass_"):
                        continue
                    self.client.delete(
                        collection.name,
                        models.FilterSelector(
                            filter=models.Filter(
                                must=[
                                    models.FieldCondition(
                                        key="document_id",
                                        match=models.MatchValue(value=document_id),
                                    )
                                ]
                            )
                        ),
                        wait=True,
                    )
        except Exception as exc:
            raise PipelineError(
                "qdrant_cleanup_failed",
                "無法確認向量已清理。請啟動 Qdrant、檢查 QDRANT_URL 後重試刪除；"
                "本機資料保留供重試。",
            ) from exc
