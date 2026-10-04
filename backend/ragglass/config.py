import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    ragglass_data_dir: Path = ROOT / ".data"
    llm_provider: str = "ollama"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "gemma4:e4b"
    llm_api_key: str = ""
    llm_timeout_seconds: float = Field(default=180, gt=0)
    llm_temperature: float = 0
    llm_max_tokens: int = Field(default=768, ge=64)
    llm_context_tokens: int = Field(default=8192, ge=1024)
    llm_keep_alive: str = "5m"
    llm_think: bool = False
    llm_json_mode: bool = True
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str = ""
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    embedding_device: str = "cpu"
    cpu_threads: int = Field(default=4, ge=1)
    chunk_tokens: int = Field(default=240, ge=32, le=400)
    chunk_overlap_tokens: int = Field(default=32, ge=0)
    retrieval_top_k: int = Field(default=5, ge=1, le=12)
    retrieval_score_threshold: float = Field(default=0.70, ge=0, le=1)
    max_upload_mb: int = Field(default=30, ge=1)
    max_pdf_pages: int = Field(default=200, ge=1)
    ingest_batch_size: int = Field(default=32, ge=1, le=256)

    def configure_paths(self):
        if not self.ragglass_data_dir.is_absolute():
            self.ragglass_data_dir = ROOT / self.ragglass_data_dir
        for key, folder in (
            ("HF_HOME", "huggingface"),
            ("TORCH_HOME", "torch"),
            ("DOCLING_CACHE_DIR", "docling"),
        ):
            os.environ.setdefault(key, str(ROOT / ".cache" / folder))
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        if self.chunk_overlap_tokens >= self.chunk_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_TOKENS")
        if self.llm_provider not in {"ollama", "openai"}:
            raise ValueError("LLM_PROVIDER must be ollama or openai")
