# RAGGlass

**See inside your RAG.**

**English** | [繁體中文](README.zh-TW.md)

A locally deployable diagnostic workbench for engineers building document RAG. Trace an answer back through retrieved evidence and parsed content to the original PDF. Inspect the exact configuration and measured stage timings, then reopen documents and runs after a restart.

The first milestone implements native-text PDF ingestion with Docling, multilingual dense retrieval with Qdrant, and grounded answers from an independent model HTTP service. The application uses real embeddings and model inference; there are no canned demo answers. The original [sample PDF](examples/ragglass-field-guide.pdf) describes a fictional Cedar pilot and includes a simple table and [six test questions](examples/questions.json), including one the document cannot answer.

## Requirements

- Linux/macOS with Python **3.12**, Node.js **20.19+**, npm, and Docker Compose. The verified host uses Ubuntu 24.04, system Python 3.12.3, Node 20.20.2, and Docker 29.3.0.
- A reachable Ollama or OpenAI-compatible model API. The verified installation reuses an existing local Ollama service and `gemma4:e4b`; the app does not start, upgrade, or manage that service.
- Internet access for first-time dependency and Docling/E5 model downloads. After downloads, parsing and embedding remain local. Point the model endpoint to a local service for local inference.
- The default Docling parser and `intfloat/multilingual-e5-small` embedding run on CPU with four threads. GPU use belongs to the separate model service. No system driver changes are required. The measured host has two NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition GPUs; see [measured verification](docs/MILESTONE.md) for evidence, limits, and timings.

## Local setup

From the repository root:

```bash
# Project-local uv bootstrap; uses the existing Python with pip.
python3 -m pip install --target .tools uv==0.8.22
export UV_CACHE_DIR="$PWD/.cache/uv"
.tools/bin/uv sync --frozen --python 3.12
npm --prefix frontend ci
cp .env.example .env
docker compose up -d qdrant
bash scripts/dev.sh
```

Open **http://127.0.0.1:5173**. The API is at **http://127.0.0.1:8000** and API documentation at `/docs`. Qdrant uses **127.0.0.1:6333** and the dedicated `ragglass_qdrant_data` Docker volume. All app ports bind to loopback. Ctrl+C stops development processes; it leaves Qdrant and data intact. For separate terminals, use:

```bash
.venv/bin/python -m uvicorn ragglass.main:app --app-dir backend --host 127.0.0.1 --port 8000
# In a second terminal:
npm --prefix frontend run dev
```

If Python 3.12 is absent, uv can download a managed interpreter into the project with `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" .tools/bin/uv python install 3.12` before syncing. System `python3.12-venv`/`ensurepip` is not required by uv. Python dependencies live in `.venv`, Node dependencies in `frontend/node_modules`, and model caches in `.cache`. Never use `sudo pip` or upgrade GPU drivers.

For a single-server built UI, stop the development API, then:

```bash
npm --prefix frontend run build
.venv/bin/python -m uvicorn ragglass.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

The API serves `frontend/dist` when present at startup. Open **http://127.0.0.1:8000**. There is no separate frontend container or hosted cloud dependency.

## Model configuration

Edit `.env` before starting the API. Defaults reuse an existing service:

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=gemma4:e4b
```

Confirm your actual available models with `curl http://127.0.0.1:11434/api/tags`. Choose an installed local model that supports instruction following and JSON output. Do not select an Ollama `:cloud` model for offline/local inference. The native Ollama adapter requests schema-constrained JSON, disables thinking by default, and records returned model/token/duration metadata. Model loading can make the first query slower; the configured timeout is 180 seconds.

For an existing vLLM or another OpenAI-compatible service:

```dotenv
LLM_PROVIDER=openai
LLM_BASE_URL=http://127.0.0.1:8001/v1
LLM_MODEL=your-served-model-name
LLM_API_KEY=
LLM_JSON_MODE=true
```

The adapter calls `/chat/completions` and requests JSON output; disable `LLM_JSON_MODE` only when that API rejects the option. The prompt still requires JSON, and validation stays mandatory. The OpenAI-compatible adapter has contract coverage; live vLLM deployment is outside this milestone because the existing Ollama service satisfies local inference. All container images in this project have explicit versions.

Embedding uses the immutable E5 revision in `.env.example`, normalized vectors, `query: ` / `passage: ` prefixes, and the model's tokenizer. Changing embedding settings selects a different Qdrant collection; reindex existing documents before querying. Docling downloads layout/table models automatically. `DOCLING_CACHE_DIR` is a download cache; `DOCLING_ARTIFACTS_PATH` is optional and must contain already downloaded models.

## Try the complete flow

1. Download the sample from the sidebar or use `examples/ragglass-field-guide.pdf`, then upload it. Watch queued → parsing → chunking → embedding → indexing → indexed. The first ingestion includes model downloads. The original PDF can be viewed during processing.
2. Ask **What is the maximum upload size for the Cedar pilot?** The expected fact is **30 MB**, from the table on **page 2**. The answer is generated live.
3. Click a source button under the answer. PDF.js jumps to the corresponding original page; available source item boxes are highlighted. Evidence cards show full chunk IDs, cosine scores, page numbers, and coordinate availability.
4. Open **Parsed content** to inspect chunks or raw Markdown/Docling JSON. Open document details for SHA-256, parser/chunk/embedding settings, and ingestion timings.
5. Inspect the execution trace, expand the run settings/prompt, or download run JSON. The run records the exact evidence, prompt, model endpoint/name/options, tokenizer revision, chunk settings, and retrieval settings, excluding API keys.
6. Ask **What is the pilot's annual electricity cost in dollars?** It must state that the document cannot confirm the answer and show no citations.
7. Restart the API and Qdrant without deleting their storage. Uploaded files, documents, and query history remain available. Click a saved run to reopen its answer, evidence, and configuration.

The UI defaults to Traditional Chinese; switch to English in the top-right selector. The language preference survives a reload. Backend actionable errors are currently in Traditional Chinese.

## Remote preview through SSH

Run this on your local computer while the application runs on the remote host:

```bash
ssh -N -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 user@your-host
```

Open `http://127.0.0.1:5173` locally (or port 8000 for the built UI). The browser calls the relative `/api` path through Vite's proxy. No public binding, reverse proxy, or cloud deployment is required. SSH tunneling instructions are provided; remote-client connectivity must be verified in your own network.

## Verification

```bash
bash scripts/check.sh
# With API, Qdrant, and the real model service running:
.venv/bin/python scripts/verify_e2e.py
npm --prefix frontend run test:e2e
# To check the built UI served directly by FastAPI:
RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e
```

Contract tests cover valid/invalid citations, malformed model output, actual TCP connection refusal, SQLite persistence, interrupted-work recovery, and secret exclusion. They use small explicitly synthetic inputs; they do not pretend to be live inference.

`verify_e2e.py` uploads the fixture, checks Docling page/coordinate mappings and known retrieved evidence, and asks all six questions through the real model. It writes measured records to ignored `.data/verification.json`. Browser tests exercise PDF upload, live question/answer, source navigation, history after reload, and language switching. They use local Google Chrome by default; alternatively run `PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/playwright" frontend/node_modules/.bin/playwright install chromium` and set `RAGGLASS_BROWSER=chromium` for tests. For a machine without an NVIDIA GPU, the API still runs on CPU; the measurement script reports GPU telemetry unavailable rather than inventing numbers.

## Data and architecture

```text
Vue + PDF.js → FastAPI → Docling → page-aware token chunks → local E5 → Qdrant
                   └─ query → E5 → retrieved evidence → model HTTP API
                                                    → citation validation → saved run
SQLite: document metadata, chunks, runs        Local files: PDFs, Markdown, Docling JSON
```

The adapters are `parser.py`, `embedding.py`, `retrieval.py`, and `llm.py`; `pipeline.py` orchestrates them. Background ingestion is serialized for predictable CPU memory use. Query workers remain separate from the UI request loop. SQLite is the metadata source of truth; Qdrant can be rebuilt from documents by reindexing. Each chunk retains all source pages, including multi-page items. Coordinates refer to original Docling source items, which can be larger than an individual token window; they are not fabricated exact phrase bounds. Missing coordinates are explicitly marked.

`.data/documents/<document-id>/` contains `original.pdf`, `parsed.md`, and `docling.json`; `.data/ragglass.sqlite3` stores metadata/chunks/runs. Back up `.data` together with the Qdrant Docker volume. `docker compose down` keeps the volume; **`docker compose down -v` deletes the vector storage**. `.env`, data, caches, dependencies, build output, and local reports are ignored by Git. The sample fixture is the only PDF intended for publication.

## Limits and next milestone

Native-text PDFs only; OCR/VLM, hybrid retrieval, reranking, formal quality metrics, a diagnostic agent, and embedding tuning are not implemented. Citation validation guarantees source membership and document/page mapping; it does not establish semantic entailment of every answer. Model refusal is prompt-based, so broad adversarial reliability still requires evaluation. This is a single-user, loopback workbench, with no authentication, distributed job queue, multi-user isolation, or production hardening. Restarted in-flight work is marked failed and can be retried rather than silently resumed. Remote vLLM, SSH client networking, scanned documents, and large corpora have not been validated on this installation.

The suggested next milestone is a repeatable before/after evaluation workflow: fixed question sets, retrieval/answer metrics, run comparisons, and a replaceable hybrid retriever/reranker. See [milestone details](docs/MILESTONE.md), [contributing](CONTRIBUTING.md), and [agent rules](AGENTS.md). English-first PRs include a Traditional Chinese summary; never commit private uploads or credentials.
