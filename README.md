# RAGGlass

**See inside your RAG.**

**English** | [繁體中文](README.zh-TW.md)

[![Checks](https://github.com/KuoFengYuan/RAGGlass/actions/workflows/checks.yml/badge.svg)](https://github.com/KuoFengYuan/RAGGlass/actions/workflows/checks.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-a44b30)](LICENSE)

**Debug document RAG by seeing the original PDF, retrieved evidence, and model answer together.**

RAGGlass is a local, open-source workbench for engineers building PDF RAG. Inspect a missing table fact, irrelevant retrieval, or an unsupported answer by tracing the actual document → parse → chunks → evidence → answer path.

- **Trace citations:** click a validated source link to its original PDF page.
- **Read and reuse results:** search/zoom/select PDF text, follow or stop queries, and copy answers or export Markdown reports.
- **Inspect parsing and retrieval:** compare Docling output and scored passages with the document.
- **Reproduce a run:** retain prompts, settings, evidence, answers, and measured timings after restarts.
- **Manage your workspace:** search documents/history and remove selected items or clear all with explicit confirmation.
- **Process PDFs with feedback:** check upload limits before transfer, follow confirmed chunk progress, and stop queued or running processing.
- **Use your model service:** real embeddings and live Ollama or compatible HTTP inference.

[Quick start](#quick-start) · [Watch the demo](#watch-the-demo) · [Illustrated usage](docs/USAGE.md) · [Deployment](docs/DEPLOYMENT.md) · [Model choices](#recommended-ollama-models)

If RAGGlass is useful for your RAG work, **[⭐ give it a star](https://github.com/KuoFengYuan/RAGGlass)**.

## Watch the demo

https://github.com/user-attachments/assets/5ebfca43-fd95-4244-a178-7e5f174f51a6

**Press Play above for the complete 84.7-second tutorial with English instructions inside the video.** Each step names what to click and what to check; pause or seek to follow along. Learn to upload a PDF, ask a question, follow a citation, inspect parsing/settings, check a refusal, reopen history, and clean up PDFs/records independently. [Follow the nine-step guide](docs/DEMO.md).

*Actual recorded inference at normal speed, using the fictional CC0 sample and its existing index. [Trace the table answer](docs/CASE_STUDY.md) · [Recording receipt](docs/media/demo-recording.json)*

See the [v0.1.0 preview](https://github.com/KuoFengYuan/RAGGlass/releases/tag/v0.1.0) for release notes and the public sample. For still images, see the [actual workbench screenshot](docs/images/workbench.png) and the illustrated guide below.

**First release:** native-text PDF ingestion with Docling, multilingual dense retrieval with Qdrant, validated source IDs, and persistent local history. The [original sample PDF](examples/ragglass-field-guide.pdf) includes a table and [six test questions](examples/questions.json), including one it cannot answer. Automated diagnosis, hybrid search, reranking, and before/after quality comparisons are planned; they are not implemented in this release.

**Stack:** Vue 3 / TypeScript / PDF.js · FastAPI · Docling · Qdrant · SQLite · independent model HTTP API.

## Documentation

| Guide | What it covers |
| --- | --- |
| [Illustrated usage](docs/USAGE.md) | Upload, status, questions, citations, parsed content, history, and five actual UI views. |
| [Cleanup guide](docs/CLEANUP.md) | Search/filter catalogs, delete PDFs or records, missing-source behavior, and cleanup verification. |
| [Reading and query controls](docs/USABILITY.md) | Query progress/cancellation, PDF search/zoom/selection, answer copying, Markdown reports, and isolated verification. |
| [Upload and processing](docs/INGESTION.md) | Local PDF checks, document progress/stop, bounded vector batches, retry behavior, and isolated validation. |
| [Video tutorial](docs/DEMO.md) | Nine numbered steps, scene times, and instructional subtitles already visible in the video. |
| [Installation and deployment](docs/DEPLOYMENT.md) | Environment, model service, Qdrant, development/built modes, optional user service, SSH, backup, updates, and troubleshooting. |
| [Measured milestone](docs/MILESTONE.md) | Real model/browser/restart results, hardware observations, timings, and limits. |
| [Table/source case study](docs/CASE_STUDY.md) | Follow a real answer to page 2 and inspect a question the document cannot answer. |
| [Share RAGGlass](docs/LAUNCH.md) | Bilingual video/cover assets, technical post drafts, first-week plan, and local traffic snapshots. |
| [Release notes](docs/RELEASE-v0.1.0.md) | First-preview capabilities, setup, evidence, and remaining limits. |
| [Contributing](CONTRIBUTING.md) | Forks, task branches, checks, bilingual PRs, and licensing. |

## Requirements

- Linux with Python **3.12**, Node.js **20.19+**, npm, and Docker Compose. The verified host uses Ubuntu 24.04, system Python 3.12.3, Node 20.20.2, and Docker 29.3.0.
- A reachable Ollama or OpenAI-compatible model API. The verified installation reuses an existing local Ollama service and `gemma4:e4b`; the app does not start, upgrade, or manage that service.
- Internet access for first-time dependency and Docling/E5 model downloads. After downloads, parsing and embedding remain local. Point the model endpoint to a local service for local inference.
- The default Docling parser and `intfloat/multilingual-e5-small` embedding run on CPU with four threads. GPU use belongs to the separate model service. No system driver changes are required. The measured host has two NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition GPUs; see [measured verification](docs/MILESTONE.md) for evidence, limits, and timings.

## Quick start

For a fresh checkout, with the prerequisites and model service available:

```bash
git clone https://github.com/KuoFengYuan/RAGGlass.git
cd RAGGlass
# Project-local uv bootstrap; uses the existing Python with pip.
python3 -m pip install --target .tools uv==0.8.22
export UV_CACHE_DIR="$PWD/.cache/uv"
.tools/bin/uv sync --frozen --python 3.12
npm --prefix frontend ci
if [ ! -f .env ]; then cp .env.example .env; fi
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

### Recommended Ollama models

Recommendations checked against official model cards and the Ollama registry on **2026-10-03**. These are candidates for this workbench, not a claim that one model is universally best. General coding/reasoning benchmarks do not establish document answer quality, citation accuracy, or refusal reliability.

| Answer model | Suggested use | Status in this installation |
| --- | --- | --- |
| [`gemma4:e4b`](https://ollama.com/library/gemma4) | **Default and verified baseline.** Start here for a compact local installation and the documented sample workflow. | Installed; real PDF/model/browser checks passed. Keep as the baseline when comparing changes. |
| [`qwen3.8:27b`](https://ollama.com/library/qwen3.8) | **First candidate to compare** for Chinese/English document questions on a GPU workstation. The official model supports configurable thinking; start with this app's thinking-disabled JSON configuration. | Installed under the exact local name **`Qwen3.8:27b`**; used by other work. RAGGlass answer quality and latency have not been measured with it. |
| [`gemma4:31b`](https://ollama.com/library/gemma4) | Larger dense-model comparison within the Gemma family when memory and latency budgets permit. | Installed; not yet evaluated in this application. |
| [`gemma4:12b`](https://ollama.com/library/gemma4:12b) | Intermediate-size candidate for machines where 27B/31B models are impractical. | Official registry entry checked; not installed or tested on this host. Confirm compatibility with your Ollama version. |

**Practical recommendation:** keep E4B as the first-release default, compare Qwen3.8-27B next, then compare Gemma4-31B if the evaluation justifies its cost. The verified host has two GPUs reporting 97,887 MiB each, but other workloads share them. Model file size is not a VRAM requirement; actual memory and latency depend on quantization, context, concurrency, and the serving engine. No resource estimate for an untested candidate is presented as a measurement.

The app currently runs `intfloat/multilingual-e5-small` locally through Sentence Transformers on CPU. Docling's layout/table models also run on CPU, with OCR disabled. Answer generation is the only model HTTP call. The following Ollama **embedding** options are recommendations for a later adapter and evaluation, not selectable answer models:

| Embedding model | Suggested use | Integration status |
| --- | --- | --- |
| [`qwen3-embedding:0.6b`](https://ollama.com/library/qwen3-embedding) | First multilingual retrieval candidate; the family supports Chinese/English and task instructions. | Not integrated or tested; requires an Ollama `/api/embed` adapter. |
| [`qwen3-embedding:4b`](https://ollama.com/library/qwen3-embedding) | Larger retrieval comparison after 0.6B, if measured recall gains justify the resources. | Not integrated or tested. |
| [`embeddinggemma:300m`](https://ollama.com/library/embeddinggemma) | Compact multilingual alternative for a future resource-conscious deployment. | Not integrated or tested; registry specifies Ollama 0.11.10 or newer. |

Embedding migration requires the correct model-specific instructions/pooling, tokenizer, vector dimensions and normalization, a new collection, full reindexing, and recalibration of retrieval thresholds. **Do not put these names in `LLM_MODEL` or simply replace the current E5 environment settings.** The E5 adapter uses E5-specific prefixes. Reranking and multimodal PDF retrieval remain future capabilities; selecting a vision-capable answer model does not enable OCR/VLM in the parser.

### Select and verify an answer model

```bash
# Inspect the existing service before downloading anything.
curl -fsS http://127.0.0.1:11434/api/tags
# Only if your selected model is missing, pull ONE candidate:
ollama pull qwen3.8:27b
# Alternatives: ollama pull gemma4:e4b / gemma4:31b / gemma4:12b
```

Copy the **exact installed name** into `.env`; this host uses `Qwen3.8:27b`, while a fresh official pull normally uses `qwen3.8:27b`. An installed model is not proof of application compatibility.

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen3.8:27b
LLM_THINK=false
LLM_CONTEXT_TOKENS=8192
LLM_MAX_TOKENS=768
LLM_TIMEOUT_SECONDS=180
LLM_TEMPERATURE=0
```

Restart **only the RAGGlass API** to load the edited settings. Verify `curl -fsS http://127.0.0.1:8000/api/config`, then run `.venv/bin/python scripts/verify_e2e.py` and the browser checks below. An answer-model change does not require document reindexing. Keep the same PDFs, questions, prompt, retrieval/chunk settings, and generation options when comparing models; include Chinese/English table questions and unanswerable questions. Inspect saved answers and citations, not just the script's pass/fail. The six fixture questions are a smoke test, not a quality ranking.

Ollama tags can change after a pull. Save the installed metadata/digests with `curl -fsS http://127.0.0.1:11434/api/tags > .data/model-tags.json` before an evaluation; `.data` is ignored. Runs store model names/options and returned metrics, but do not archive model weights. Preserve the evaluated weights for reproduction. The checked first-release E4B digest and actual timings are in the [milestone record](docs/MILESTONE.md). No model download, default-model replacement, or shared Ollama restart was performed for this recommendation update.

## Try the complete flow

1. Download the sample from the document toolbar or use `examples/ragglass-field-guide.pdf`, then upload it. The browser checks native text, encryption, and configured size/page limits before transfer. Watch queued → parsing → chunking, then embedding/indexing batches → indexed, with elapsed time and confirmed chunk counts. Stop processing if needed; the original PDF can be viewed during processing. The first ingestion includes model downloads.
2. Ask **What is the maximum upload size for the Cedar pilot?** The expected fact is **30 MB**, from the table on **page 2**. The answer is generated live.
3. Click a source button under the answer. PDF.js jumps to the corresponding original page; available source item boxes are highlighted. Select a retrieved passage to expand its full text, chunk ID, cosine score, page numbers, and coordinate availability. The page rail also lets you browse original pages directly.
4. Open **Parsed content** to inspect chunks or raw Markdown/Docling JSON. Open document details for SHA-256, parser/chunk/embedding settings, and ingestion timings.
5. Inspect the execution trace, expand the run settings/prompt, or download run JSON. The run records the exact evidence, prompt, model endpoint/name/options, tokenizer revision, chunk settings, and retrieval settings, excluding API keys.
6. Ask **What is the pilot's annual electricity cost in dollars?** It must state that the document cannot confirm the answer and show no citations.
7. Restart the API and Qdrant without deleting their storage. Uploaded files, documents, and query history remain available. Open **Run history** in the top navigation and select a saved run to reopen its answer, evidence, and configuration.

8. To remove data, open **Document library** or **Run history**: search/filter, delete a row, select items, or **Clear all**, then review and confirm the scope. PDF deletion removes originals/parses/chunks/vectors; history cleanup removes saved queries/results independently. [Read the cleanup guide](docs/CLEANUP.md).

The workspace places the original PDF on the left and a query/answer/evidence inspector on the right, with measured execution timings along the bottom. **Document library** and **Run history** open list dialogs from the top navigation; the active document can also be changed in the document selector. On narrow screens, the PDF and inspector stack vertically.

The UI defaults to Traditional Chinese; switch to English in the top-right selector. The language preference survives a reload. Cleanup errors are localized; other backend actionable errors currently use Traditional Chinese.

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

`verify_e2e.py` uploads the fixture, checks Docling page/coordinate mappings and known retrieved evidence, and asks all six questions through the real model. It writes measured records to ignored `.data/verification.json`. Browser tests exercise PDF upload, live question/answer, source navigation, history after reload, language switching, document/page navigation, keyboard dialog dismissal, retrieval input validation, and a 390-pixel mobile layout. They use local Google Chrome by default; alternatively run `PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/playwright" frontend/node_modules/.bin/playwright install chromium` and set `RAGGLASS_BROWSER=chromium` for tests. For a machine without an NVIDIA GPU, the API still runs on CPU; the measurement script reports GPU telemetry unavailable rather than inventing numbers.

## Data and architecture

```text
Vue + PDF.js → FastAPI → Docling → page-aware token chunks → local E5 → Qdrant
                   └─ query → E5 → retrieved evidence → model HTTP API
                                                    → citation validation → saved run
SQLite: document metadata, chunks, runs        Local files: PDFs, Markdown, Docling JSON
```

The adapters are `parser.py`, `embedding.py`, `retrieval.py`, and `llm.py`; `pipeline.py` orchestrates them. A single document worker manages queued jobs and cooperative stops. Each bounded vector batch is written and released before the next one; parsing and text metadata still use memory for the whole document. Query workers remain separate from the UI request loop. SQLite is the metadata source of truth; Qdrant can be rebuilt from documents by reindexing. Each chunk retains all source pages, including multi-page items. Coordinates refer to original Docling source items, which can be larger than an individual token window; they are not fabricated exact phrase bounds. Missing coordinates are explicitly marked.

`.data/documents/<document-id>/` contains `original.pdf`, `parsed.md`, and `docling.json`; `.data/ragglass.sqlite3` stores metadata/chunks/runs. Back up `.data` together with the Qdrant Docker volume. `docker compose down` keeps the volume; **`docker compose down -v` deletes the vector storage**. `.env`, data, caches, dependencies, build output, and local reports are ignored by Git. The sample fixture is the only PDF intended for publication.

## Limits and next milestone

Native-text PDFs only; OCR/VLM, hybrid retrieval, reranking, formal quality metrics, a diagnostic agent, and embedding tuning are not implemented. Citation validation guarantees source membership and document/page mapping; it does not establish semantic entailment of every answer. Model refusal is prompt-based, so broad adversarial reliability still requires evaluation. This is a single-user, loopback workbench, with no authentication, distributed job queue, multi-user isolation, or production hardening. Restarted in-flight work is marked failed and can be retried rather than silently resumed. Remote vLLM, SSH client networking, scanned documents, and large corpora have not been validated on this installation.

The suggested next milestone is a repeatable before/after evaluation workflow: fixed question sets, retrieval/answer metrics, run comparisons, and a replaceable hybrid retriever/reranker. See [milestone details](docs/MILESTONE.md), [contributing](CONTRIBUTING.md), and [agent rules](AGENTS.md). English-first PRs include a Traditional Chinese summary; never commit private uploads or credentials.

## License and contributions

RAGGlass is open source. Unless otherwise noted, the application code and project documentation are released under the [MIT License](LICENSE). The original sample PDF and its generator remain [CC0 1.0](examples/README.md). Third-party dependencies and model weights retain their respective licenses; weights are not distributed in this repository.

Issues and pull requests are welcome. See [Contributing](CONTRIBUTING.md) for setup, branch naming, validation, and the bilingual PR workflow. Use the public fixture or a sanitized reproduction when reporting a problem; keep private documents and credentials out of issues and commits.
