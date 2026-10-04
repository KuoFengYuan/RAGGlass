import hashlib
import json
import threading

from qdrant_client import QdrantClient, models

from .errors import PipelineError
from .keyword import KeywordRetriever

RRF_K = 60
DEFAULT_CANDIDATE_K = 20
MODES = {"dense": "dense-cosine", "keyword": "bm25-local", "hybrid": "hybrid-rrf"}


def snapshot(mode, top_k, threshold, candidate_k, collection):
    return {
        "mode": mode,
        "strategy": MODES[mode],
        "top_k": top_k,
        "score_threshold": threshold,
        "threshold_scope": "dense-cosine-only",
        "candidate_k": candidate_k,
        "candidate_scope": "hybrid-branches-only",
        "collection": collection,
        "keyword": KeywordRetriever.snapshot(),
        "fusion": {
            "algorithm": "reciprocal-rank-fusion",
            "k": RRF_K,
            "weights": [1, 1],
            "tie_break": "keyword-score-desc,dense-rank-asc,chunk-id-asc",
        },
    }


def rank_evidence(dense, keyword, mode, top_k):
    """Fuse ranks; tie-break within the BM25 scale, then dense rank and stable ID.

    Cosine and BM25 scores are never averaged or compared against each other.
    """
    items = {}
    for name, results in (("dense", dense), ("keyword", keyword)):
        for result in results:
            item = items.setdefault(result["id"], {**result, "retrieval_scores": {}})
            item["retrieval_scores"][name] = {"rank": result["rank"], "score": result["score"]}
            if name == "keyword":
                item["matched_terms"] = result["matched_terms"]
    if mode == "hybrid":
        for item in items.values():
            item["score"] = sum(1 / (RRF_K + s["rank"]) for s in item["retrieval_scores"].values())
        ordered = sorted(
            items.values(),
            key=lambda item: (
                -item["score"],
                -item["retrieval_scores"].get("keyword", {}).get("score", 0),
                item["retrieval_scores"].get("dense", {}).get("rank", float("inf")),
                item["id"],
            ),
        )
    else:
        ordered = [items[result["id"]] for result in (dense if mode == "dense" else keyword)]
    return [
        {
            **item,
            "rank": rank,
            "score_kind": {"dense": "cosine", "keyword": "bm25", "hybrid": "rrf"}[mode],
        }
        for rank, item in enumerate(ordered[:top_k], 1)
    ]


def candidate_trace(items):
    return [
        {key: item[key] for key in ("id", "document_id", "filename", "pages", "rank", "score")}
        | ({"matched_terms": item["matched_terms"]} if "matched_terms" in item else {})
        for item in items
    ]


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
