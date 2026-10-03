import threading

from .config import Settings


class Embedder:
    """Local E5 adapter. Query/passage prefixes and immutable revision are recorded."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None
        self._lock = threading.RLock()

    @property
    def model(self):
        with self._lock:
            if self._model is None:
                import torch
                from sentence_transformers import SentenceTransformer

                torch.set_num_threads(self.settings.cpu_threads)
                self._model = SentenceTransformer(
                    self.settings.embedding_model,
                    revision=self.settings.embedding_revision,
                    device=self.settings.embedding_device,
                )
            return self._model

    def encode(self, texts, query=False):
        prefix = "query: " if query else "passage: "
        with self._lock:
            return self.model.encode(
                [prefix + t for t in texts],
                normalize_embeddings=True,
                batch_size=16,
                show_progress_bar=False,
            ).tolist()

    def snapshot(self):
        return {
            "model": self.settings.embedding_model,
            "revision": self.settings.embedding_revision,
            "device": self.settings.embedding_device,
            "normalize": True,
            "query_prefix": "query: ",
            "passage_prefix": "passage: ",
        }
