# Install and deploy RAGGlass

**English** | [繁體中文](DEPLOYMENT.zh-TW.md)

This guide runs RAGGlass on one Linux host, with CPU parsing/embedding, persistent Docker Qdrant, and an independent model HTTP service. Choose development mode while editing, or a built frontend served by FastAPI for ordinary use. Both bind to loopback; access a remote host through SSH. The application is a single-user workbench without authentication, so the supported preview path keeps these ports private.

For the illustrated workflow, see [Using RAGGlass](USAGE.md). Model recommendations and their verification status are in the [README](../README.md#recommended-ollama-models).

## Services and requirements

| Component | Role | Default address / storage |
| --- | --- | --- |
| FastAPI | Uploads, ingestion, queries, history; serves the built UI | `127.0.0.1:8000`; `.data` |
| Vite | Development frontend and `/api` proxy | `127.0.0.1:5173`; development only |
| Qdrant v1.15.5 | Dense vector index | `127.0.0.1:6333`; `ragglass_qdrant_data` volume |
| Ollama or compatible API | Answer generation, separately managed | Ollama default `127.0.0.1:11434` |
| Docling / E5 | Native-text parsing and embeddings | CPU, project `.cache` |

The validated host is **Ubuntu 24.04 x86_64, Python 3.12.3, Node 20.20.2, npm 10.8.2, Docker 29.3.0 / Compose v5.1.0**. Use Python **3.12** and Node **20.19+**. macOS/Windows native installation is unverified, including compatibility of the locked `torch==2.8.0+cpu` wheels; you can use either as the browser/SSH client of a Linux host.

A GPU is not required for FastAPI/Docling/E5. The model service must have sufficient CPU/GPU resources for its selected model; reuse an installed service and leave other GPU jobs running. First setup needs internet for dependencies and model artifacts. After downloads, the default path stays local when the LLM endpoint is local.

Inspect before starting:

```bash
python3 --version
node --version
npm --version
docker --version
docker compose version
docker ps
ss -ltnp
free -h
df -h .
# If available, inspect GPU model, memory, and existing workloads:
nvidia-smi
```

Do not run driver upgrades for this application. If Docker permissions or the required interpreter/runtime are missing, have the host administrator resolve those specific prerequisites. Official [Docker Compose installation](https://docs.docker.com/compose/install/) and [Ollama Linux installation](https://docs.ollama.com/linux) are separate from this repository's application setup.

## 1. Create a project-local environment

For a fresh checkout:

```bash
git clone https://github.com/KuoFengYuan/RAGGlass.git
cd RAGGlass
python3 -m pip install --target .tools uv==0.8.22
export UV_CACHE_DIR="$PWD/.cache/uv"
.tools/bin/uv sync --frozen --python 3.12
npm --prefix frontend ci
if [ ! -f .env ]; then cp .env.example .env; fi
```

Python dependencies go into `.venv`, Node dependencies into `frontend/node_modules`, and downloads into project caches. Keep `uv.lock` and `frontend/package-lock.json` unchanged for reproduction. The pip bootstrap requires a Python with pip; uv creates the virtual environment even when system Python lacks `ensurepip`.

If Python 3.12 is unavailable but your bootstrap Python works:

```bash
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" .tools/bin/uv python install 3.12
.tools/bin/uv sync --frozen --python 3.12
```

Edit `.env` with your actual model settings. `.env` and runtime data are ignored by Git. Do not overwrite an existing `.env` during updates. Environment variables supplied by the process take precedence over the file.

## 2. Connect a separate model service

Check the existing Ollama first:

```bash
curl -fsS http://127.0.0.1:11434/api/tags
```

Use an exact installed name, including this host's `Qwen3.8:27b` alias if you choose that candidate. The measured default is:

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=gemma4:e4b
LLM_API_KEY=
LLM_THINK=false
LLM_CONTEXT_TOKENS=8192
LLM_MAX_TOKENS=768
LLM_TIMEOUT_SECONDS=180
```

Only when no service is running and the Ollama binary is already installed, an optional separate terminal can run:

```bash
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/.cache/ollama" ollama serve
# Another terminal, only if the chosen model is missing:
ollama pull gemma4:e4b
```

These optional new-server commands are instructions, not a claim that this installation started a second service. Existing Ollama deployments keep their own model paths. Do not restart a shared model service to apply RAGGlass settings; restart only the API. Select local models for offline inference; `:cloud` variants make remote requests.

For an existing vLLM or another compatible service:

```dotenv
LLM_PROVIDER=openai
LLM_BASE_URL=http://127.0.0.1:8001/v1
LLM_MODEL=your-served-model-name
LLM_API_KEY=
LLM_JSON_MODE=true
```

Supply an API key only if that service requires one. Keep it in `.env`, not in a URL or commit. Native Ollama was tested live; the compatible adapter has synthetic contract coverage, and new vLLM deployment is unverified. Do not use an embedding model as `LLM_MODEL`.

## 3. Start persistent Qdrant

```bash
docker compose up -d qdrant
docker compose ps
curl -fsS http://127.0.0.1:6333/healthz
```

[compose.yaml](../compose.yaml) pins `qdrant/qdrant:v1.15.5` and publishes only loopback port 6333. The default Compose project name is `ragglass`; Docker creates and reuses `ragglass_qdrant_data`. If you override the project name, inspect the resulting volume name before backup/restore. `restart: unless-stopped` applies to Qdrant, not to the manually started API or model service.

## 4A. Development mode

```bash
bash scripts/dev.sh
```

Open **http://127.0.0.1:5173**. The script starts FastAPI and Vite; Ctrl+C stops these project processes, leaving Qdrant/data intact. It requires `.venv` and frontend dependencies from step 1.

For two terminals instead:

```bash
# Terminal 1, repository root:
.venv/bin/python -m uvicorn ragglass.main:app --app-dir backend --host 127.0.0.1 --port 8000
# Terminal 2, repository root:
npm --prefix frontend run dev
```

Use one startup method at a time. An already running API on 8000 or Vite on 5173 must not be duplicated.

## 4B. Built frontend served by FastAPI

Stop this project's development API first. Then, from the repository root:

```bash
npm --prefix frontend run build
.venv/bin/python -m uvicorn ragglass.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. `frontend/dist` must exist before API startup; this mode needs no Vite process. The same server provides `/api` and `/docs`. Start from the repository root so relative cache paths resolve consistently. This is the verified deployment path; Compose currently runs Qdrant only, not the whole application.

### Optional Linux user service

[deploy/ragglass.service](../deploy/ragglass.service) runs the built API without root. It assumes a checkout at `~/repo/RAGGlass`; change **both** `WorkingDirectory` and `ExecStart` if your path differs. Build and configure the app first, ensure Qdrant/model service are available, and stop a manually running copy before activation.

```bash
mkdir -p "$HOME/.config/systemd/user"
cp deploy/ragglass.service "$HOME/.config/systemd/user/ragglass.service"
# Edit the installed unit if your checkout is elsewhere.
systemd-analyze --user verify "$HOME/.config/systemd/user/ragglass.service"
systemctl --user daemon-reload
systemctl --user enable --now ragglass.service
systemctl --user status ragglass.service
journalctl --user -u ragglass.service -f
```

After an app/settings update, use `systemctl --user restart ragglass.service`. To stop it, use `systemctl --user stop ragglass.service`. The unit restarts a failed API; it does not start/manage Docker or Ollama. User-service startup outside a login session depends on the host's systemd user-session configuration. This template was syntax-checked on the measured host; service activation, logout, and reboot behavior were not tested or enabled there.

## 5. Verify readiness and the complete workflow

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/config
bash scripts/check.sh
.venv/bin/python scripts/verify_e2e.py
```

Health should report `qdrant: ready` and `llm: ready`; `/api/config` shows the loaded settings without API keys. It is not a GPU/quality benchmark. Open the interface, upload the sample, wait for Indexed, ask the upload-limit question, click page-2 citation, and reopen it from Run history. Follow the [illustrated guide](USAGE.md).

Browser checks:

```bash
npm --prefix frontend run test:e2e
RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e
```

The first targets development port 5173, the second the built port 8000. Chrome is used by default. If missing, install project-local Chromium:

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/playwright" frontend/node_modules/.bin/playwright install chromium
RAGGLASS_BROWSER=chromium RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e
```

Linux browser OS libraries may need administrator installation; that affects browser testing, not the API. The screenshot capture script uses the same browser choice.

## 6. Preview a remote host with SSH

Run on your **own computer**, keeping the application bound to loopback on the host:

```bash
# Built interface:
ssh -N -L 8000:127.0.0.1:8000 user@your-host
# Development interface, alternative:
ssh -N -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 user@your-host
```

Open the corresponding local browser port. If local 8000 is occupied, map `-L 18000:127.0.0.1:8000` and open `http://127.0.0.1:18000`. The built interface uses relative `/api` URLs, so that mapping works without frontend edits. Qdrant and Ollama do not need browser-facing tunnels.

SSH-client networking was not verified from another machine during this milestone. A public GitHub repository does not make your running app or uploaded PDFs public. Public/multi-user web hosting requires additional authentication, access isolation, and deployment work; it is outside this release.

## 7. Preserve, back up, and update data

| Path / volume | Contents | Persistence |
| --- | --- | --- |
| `.data/ragglass.sqlite3` | Documents, chunks, runs, prompts/settings, evidence, errors, timings | Back up with the document files. |
| `.data/documents/` | Original PDFs, parsed Markdown, Docling JSON | Back up together with SQLite. |
| `ragglass_qdrant_data` | Vector collections | Keep volume or rebuild by reindexing. |
| `.cache/` | Downloaded parser/embedding artifacts | Retain for offline use; can be downloaded again. |
| `.env` | Endpoints/options and optional secrets | Preserve separately and privately. |

`docker compose stop qdrant` and `docker compose down` preserve the volume. **`docker compose down -v` deletes it.** Do not delete `.data` if you want to keep uploaded files/history.

For a consistent backup, stop only the RAGGlass API, then stop this project's Qdrant. The following uses the already pinned Qdrant image as a tar helper:

```bash
docker compose stop qdrant
ragglass_backup_dir="$PWD/.data/backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$ragglass_backup_dir"
tar --exclude=.data/backups -czf "$ragglass_backup_dir/data.tgz" .data
docker run --rm --entrypoint tar \
  --mount type=volume,src=ragglass_qdrant_data,dst=/storage,readonly \
  qdrant/qdrant:v1.15.5 -czf - -C /storage . > "$ragglass_backup_dir/qdrant.tgz"
docker compose up -d qdrant
# Restart the API using your chosen startup method.
```

Keep an additional copy outside the host. To restore, use a fresh checkout and empty destination volume, with API/Qdrant stopped. Set `ragglass_backup_dir` to the actual archive directory:

```bash
tar -xzf "$ragglass_backup_dir/data.tgz" -C .
docker volume create ragglass_qdrant_data
docker run --rm -i --entrypoint tar \
  --mount type=volume,src=ragglass_qdrant_data,dst=/storage \
  qdrant/qdrant:v1.15.5 -xzf - -C /storage . < "$ragglass_backup_dir/qdrant.tgz"
```

Restore your private `.env`, use matching embedding settings, and start the services. These are recovery instructions; a full archive/restore was not executed on this installation. The Qdrant image's tar availability and the actual API/Qdrant restart persistence were verified. Docker documents the [volume lifecycle and backup mechanism](https://docs.docker.com/engine/storage/volumes/).

For a source update, preserve local work and back up before stopping the API:

```bash
git pull --ff-only
export UV_CACHE_DIR="$PWD/.cache/uv"
.tools/bin/uv sync --frozen --python 3.12
npm --prefix frontend ci
bash scripts/check.sh
# Built mode: restart the API after the check script builds frontend/dist.
```

Do not recopy `.env` over your settings. An answer-model change needs an API restart; an embedding/chunk change needs reindexing. Old query snapshots remain available.

## Troubleshooting

| Symptom | Check / action |
| --- | --- |
| Browser cannot reach backend | Confirm the API runs on 8000; in development confirm Vite also runs on 5173. Check SSH mapping if remote. |
| Port already in use | Inspect `ss -ltnp`; use the existing project instance or stop only the owned instance. Preserve unrelated services. |
| Model not available | Inspect `/api/tags`, copy the exact installed name into `.env`, restart the API. Cloud and embedding models have different roles. |
| `llm_unavailable` / timeout | Check model endpoint, service logs, available resources, and `LLM_TIMEOUT_SECONDS`. Evidence and the failed run are saved. |
| `invalid_model_response` / `invalid_citation` | Inspect the saved raw response/prompt; retry or choose a compatible JSON-output model. Unknown citation IDs are rejected. |
| Qdrant unavailable | Check `docker compose ps`, `docker compose logs qdrant`, port 6333 and `QDRANT_URL`; start this project container. |
| Parsing fails | Use an unencrypted native-text PDF within configured limits; inspect document error and retry Reindex after resolving it. OCR is disabled. |
| First ingestion is slow | Check download access/disk space and project cache directories. Later loads can reuse the artifacts. |
| PDF does not render | Use the original PDF link, check the browser console/network and stored document availability. |
| No evidence / insufficient answer | Inspect parsed chunks, wording, Top K/score threshold. Refusal is appropriate when the document lacks the fact. |
| Embedding configuration changed | Reindex existing documents for the new vector space; do not mix spaces or apply E5 prefixes to an incompatible model. |
| Interrupted indexing after restart | Interrupted jobs become Failed; use Reindex. Completed documents/history remain stored. |

Observed checks and limitations are recorded in [MILESTONE.md](MILESTONE.md). Return to [README](../README.md).
