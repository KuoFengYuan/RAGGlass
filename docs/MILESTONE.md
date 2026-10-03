# Milestone 1: an executable document RAG workbench

**English** | [繁體中文](MILESTONE.zh-TW.md)

Validation date: **2026-10-03**, Asia/Taipei. The initial directory was empty, without Git or AGENTS.md. The project now contains a Vue/PDF.js workbench, FastAPI application, independent parser/embedding/retrieval/model adapters, local persistence, pinned dependencies, Qdrant Compose storage, a CC0 fixture, automated checks, and bilingual contribution rules.

## Measured host and choices

| Item | Observation |
| --- | --- |
| OS | Ubuntu 24.04.4 LTS, Linux 6.17.0-1023-oem, x86_64 |
| GPUs | 2 × NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition |
| GPU memory | 97,887 MiB each, as reported by nvidia-smi |
| Driver | 595.71.05; nvidia-smi reported CUDA compatibility 13.2 |
| Initial GPU activity | GPU 0: 895 MiB including a Python process using 856 MiB; GPU 1: 156 MiB. Both utilization samples were 0%. |
| RAM | 502 GiB total; 480 GiB available at initial inspection |
| Disk | 1.6 TB available on the workspace filesystem at initial inspection |
| Python | Default 3.13.12; project uses existing `/usr/bin/python3.12` (3.12.3) |
| Node/npm | 20.20.2 / 10.8.2 |
| Docker/Compose | 29.3.0 / v5.1.0 |
| Reused model service | Existing loopback Ollama at port 11434, installed `gemma4:e4b` |

No driver, existing container, or unrelated service was changed. The default Python 3.12 lacked ensurepip; project-local uv created `.venv` successfully. Torch 2.8.0 CPU wheels, four CPU threads, and immutable `intfloat/multilingual-e5-small` revision `614241f622f53c4eeff9890bdc4f31cfecc418b3` avoid CUDA package compatibility and extra parser/embedding GPU use. Docling 2.60.1 runs native-text layout/table parsing with OCR disabled. Qdrant is pinned to `v1.15.5`. Vite is pinned to `7.3.6`; `npm audit --audit-level=high` reported **0 vulnerabilities** after replacing the initially selected older version.

## Real PDF/model verification

`scripts/verify_e2e.py` ran against the actual API, Docling, E5, Docker Qdrant, and existing Ollama. No responses or embeddings were mocked. The three-page original fixture describes fictional facts and quotas, not deployment measurements.

- Document SHA-256: `878bfa94da33d16c947f174d12560e3f7b4efa807cbd0b189f0841af7db58d8a`.
- Parsed **3 pages**, indexed **6 chunks**; every chunk retained the document hash, valid source page, and available original coordinates.
- Verified the page-1 maintainer and page-2 table evidence against the actual PDF text.
- Verified all answer citations were retrieved chunk IDs mapping to the actual uploaded document and expected source page.
- Saved exact prompts, evidence, model options, tokenizer/chunk/retrieval settings, raw completion, model response metadata, and actual stage timings.

First successful ingestion included model downloads and initialization:

| Stage | Measured time |
| --- | ---: |
| Docling parsing | 21,886.26 ms |
| Tokenizer initialization and chunking | 13,990.88 ms |
| Passage embedding | 123.00 ms |
| Qdrant indexing | 142.75 ms |
| Total ingestion | 36,151.55 ms |

The chunking stage includes the first embedding model/tokenizer load; these are wall-clock measurements of this run, not a pure tokenizer benchmark.

| Real-model question | Verified result | Total time |
| --- | --- | ---: |
| Maximum upload size? | 30 MB; page 2 | 7,446.41 ms |
| Chunk overlap? | 32 tokens; page 2 | 877.70 ms |
| Who maintains the pilot? | Mira Chen; page 1 | 809.50 ms |
| Does it support OCR? | Disabled; page 1 | 990.36 ms |
| Where are metadata/history stored? | SQLite; page 1 | 1,044.51 ms |
| Annual electricity cost? | Cannot confirm; no citations | 856.21 ms |

The first answer's generation stage was 7,425.12 ms; the model service reported a 6,860.39 ms model-load duration. Later query embedding stages measured 10.48–14.20 ms, retrieval 4.79–6.44 ms, and generation 791.22–1,025.62 ms. These are six samples from a small PDF, not a formal benchmark.

GPU snapshots during these questions:

| Snapshot | GPU 0 | GPU 1 |
| --- | --- | --- |
| Before the six questions | 6,239 MiB used; 0% utilization | 36,906 MiB used; 86% utilization |
| After the six questions | 11,284 MiB used; 91% utilization | 36,906 MiB used; 0% utilization |

These are aggregate instantaneous snapshots, including concurrent unrelated work. Ollama also reported a loaded `Qwen3.8:27b` belonging to other activity; it was left running. Do not attribute the total GPU memory delta to RAGGlass. For `gemma4:e4b`, Ollama reported `size_vram=3367921253` bytes (**3.1366 GiB**) at context length 8192, with model digest `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb`. This is the model service's report, not an isolated allocation benchmark.

## Other verification

- **11 passing contract/API tests**: exact citation mapping, invalid IDs, unsupported claims without citations, malformed JSON, real TCP refusal, SQLite reopen, interrupted-work recovery, secret exclusion, synthetic OpenAI wire-format compatibility, invalid/encrypted uploads, missing documents/empty questions. The OpenAI wire-format fixture is explicitly synthetic; the native Ollama end-to-end test is real.
- **1 passing Chrome browser test**: actual PDF upload, live model question, answer, source button to page 2, source-coordinate highlight, history after reload, parsed chunks, and persistent bilingual UI. It completed in **7.8 s** for that execution.
- `scripts/verify_failure.py` passed with real E5/Qdrant retrieval and an unreachable LLM endpoint. The API returned an actionable `llm_unavailable` run, preserved evidence/prompt/timings in SQLite, and exposed the saved failed run. The shared model service was never stopped.
- The default Traditional Chinese question was verified against the English PDF: `Cedar 試用方案的上傳容量上限是多少？` returned `Cedar 試用方案的每份 PDF 文件最大上傳大小限制為 30 MB。`, with a page-2 citation, in **1,001.11 ms**. This additional run is saved in `.data/chinese-verification.json`.
- After the final formatting changes and actual service restart, the Chrome test passed again on the development UI in **3.8 s**. The built FastAPI UI is separately tested with `RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e`.
- TypeScript validation and Vite production build passed. Ruff lint/format and Prettier passed. `bash scripts/check.sh` passed in full, and `git diff --cached --check` passed. Local records and the browser screenshot are in ignored `.data/`.

## Document inspection layout and model recommendations

The subsequent update replaces the persistent document/history sidebar with a horizontal masthead and document/history dialogs. The original PDF occupies the main reading area, with a page rail and parsed-content tab. The adjacent inspector contains the query, answer, validated source links, and expandable retrieved passages; real stage timings appear at the bottom. The warm paper/charcoal/rust styling and prism mark are implemented in local CSS/SVG, with no external fonts or image service. The UI keeps its Traditional Chinese default and persistent English switch. Blank or out-of-range retrieval inputs disable submission, including the keyboard shortcut.

Verification on **2026-10-03** after this change:

- `bash scripts/check.sh` passed: **11 contract/API tests**, Ruff, Prettier, TypeScript, Vite, and bilingual files.
- **2 Chrome tests passed on each interface**: development (`npm --prefix frontend run test:e2e`, **6.4 s**) and built FastAPI UI (`RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e`, **4.9 s**). Checks include live inference, citation/page highlighting, saved history, parsed content, language persistence, document catalog, Escape/focus restoration, invalid retrieval input, and a 390 × 844 viewport with a resized PDF and no document-wide horizontal overflow.
- `.venv/bin/python scripts/verify_e2e.py` again passed all **6 real-model questions**. In fixture order, total query times were **772.06, 1,166.68, 815.05, 924.18, 818.73, and 838.34 ms**. This upload reused the already indexed sample; it did not remeasure ingestion. The electricity-cost answer was refused without citations.
- Before/after snapshots for that run were both GPU 0 **11,284 MiB / 0%** and GPU 1 **36,906 MiB / 95%**. These aggregate snapshots include other GPU work and do not measure the application's peak usage.
- The README screenshot is an actual built-interface run using only the publishable fictional fixture. Local screenshots/reports remain under `.data`; only the selected documentation image is committed.

Both READMEs now describe answer-model recommendations, exact local versus registry names, switching/reproduction steps, and future Ollama embedding candidates with official sources checked on the same date. `gemma4:e4b` remains the measured default. Installed `Qwen3.8:27b` and `gemma4:31b` are comparison candidates; `gemma4:12b` and Ollama embeddings are untested. No recommended alternative was downloaded, substituted, benchmarked, or presented as proven better. Shared model services and unrelated workloads were preserved.

## Persistence and delivery

The SQLite reopen contract passed. `scripts/verify_restart.py --api-pid 2758755` then actually stopped only this project's verified API, restarted the project's Qdrant container, and started a new API process. **The uploaded document and all seven existing runs were preserved exactly; Qdrant retained all six points.** A new real-model query returned **30 MB** with a page-2 citation after restart. The built UI at port 8000 returned HTTP 200. The new API PID was 2769439. Process IDs identify this execution only; do not reuse them to restart a later session.

The real-stack reproduction commands are `.venv/bin/python scripts/verify_e2e.py`, `.venv/bin/python scripts/verify_failure.py`, and, on Linux with the actual current project API PID, `.venv/bin/python scripts/verify_restart.py --api-pid PID`. The last command deliberately restarts the API and this project's Qdrant; it verifies ownership before sending a signal. Logs and machine-readable records are `.data/backend.log`, `.data/verification.json`, `.data/failure-verification.json`, and `.data/restart-verification.json`. `npm --prefix frontend run test:e2e` writes a local screenshot to `.data/workbench.png`.

Local repository workflow: initial governance commit on `main`, implementation on `Feature/first-rag-milestone`, English commit subject and bilingual PR draft. At initial milestone completion, the owner had deferred publication and no remote PR existed. The owner subsequently authorized the first GitHub delivery together with the layout and model-guide update. Follow [AGENTS.md](../AGENTS.md) for subsequent push/PR/check/review/merge work.

The owner then requested an open-source release. A canonical MIT license was added for application code/documentation, while the original fixture/generator retain CC0. Both READMEs and contribution guides now explain licensing and the fork/PR workflow. GitHub visibility is changed only within this explicitly authorized release.

The release documentation adds full English/Traditional Chinese usage and deployment guides, ten inspected actual UI captures, and a guarded screenshot reproduction script. `node scripts/capture_ui_docs.mjs` completed with live English and Chinese sample answers; query totals were 5,153.27 ms and 885.26 ms respectively. `systemd-analyze --user verify deploy/ragglass.service` passed. The existing API was left running; the optional user service, remote SSH client, and full backup/restore were not activated or claimed as tested. README purpose/features/quick-start links and the GitHub About/topics support discovery without claiming stars or exposure results.

## Bilingual launch materials

On **2026-10-03 UTC**, the final `node scripts/capture_demo.mjs` execution verified two new real `gemma4:e4b` queries in Chrome and exported English/Traditional Chinese captioned H.264 videos (**54.791667 s**, 1440 × 1000, normal speed), two ten-second GIF excerpts, and a public capture receipt. It verified 30 MB with a retrieved source on page 2, source boxes, parsed table, settings, a refusal without citations, and saved history. Total query times were **5,177.93 ms** and **898.10 ms**. The first query's Ollama load duration was **4,626.75 ms**; this is not a warm-inference benchmark. The recording reused the sample's existing index and measured no isolated GPU usage.

`node scripts/render_social_preview.mjs` generated both 1280 × 640 covers under 1 MB using actual interface captures. `scripts/record_traffic.py` fetched a real read-only GitHub baseline and stored it under ignored `.data/traffic/`. The new bilingual sharing guide, post drafts, table/source case study, release notes, and animated README explain how to try, reproduce, share, and measure this preview. A prepared Social preview file does not set GitHub's image property; its documented web upload is a manual step. Social posts and recurring automation were not sent or scheduled. Videos/subtitles are release attachments; raw footage remains local.


## Document and history cleanup

On **2026-10-04, Asia/Taipei**, the document/history catalogs gained literal search, status filters, single deletion, checkbox selection and confirmed clearing. History uses server pagination (50/page) and a complete count; clearing is independent of displayed pages. PDF cleanup removes original/parse files, SQLite chunks/metadata and matching vectors in all RAGGlass collections. History cleanup removes the saved full record independently. Retained runs label missing originals and disable unavailable citations while keeping saved evidence readable.

- Six new synthetic cleanup contracts passed: scoped deletion and SQLite reopen, real Qdrant TCP failure/retry, busy/count guards, 126-record search/pagination/full cleanup, explicit vector-filter contracts across old collections, and invalid path/interrupted cleanup. Together with the original tests, there are **17 Python tests**. Synthetic adapters are clearly labeled.
- `.venv/bin/python scripts/verify_cleanup.py --browser` passed on an owned disposable API with real Docling/E5/Qdrant/Ollama. It verified page/table evidence, live 30 MB answer and page-2 citation, real unreachable-model error, vector removal in current and test old collections, preservation of another document, retained history with missing sources, re-upload/new ID, and actual API restarts before/after deletion.
- Actual first/variant/re-upload ingestion totals were **8,382.47 / 2,039.51 / 8,503.26 ms**. The live answer total was **4,490.48 ms**, including **4,469.13 ms** generation; these are individual runs, not benchmarks. The unreachable-model run total was **4,631.51 ms**, including CPU embedding initialization after a fresh API process.
- The two original Chrome tests passed against the built disposable interface in **17.8 s** total; the new bilingual cleanup/confirmation/missing-source/mobile test passed in **10.9 s**. It made two real model queries, reviewed actual cleanup screens, and checked reload after complete cleanup. The original owner workspace's document IDs, run states and vector counts stayed unchanged.

Coordination requires one API process per data directory. Filesystem/vector operations are not a distributed atomic transaction; failed items remain actionable and batches can partially succeed. SQLite cleanup is logical deletion, without a secure-erasure guarantee. GPU usage was not measured for this update. See the [cleanup guide](CLEANUP.md) for semantics and reproduction.


## Current-interface media and additional verification

The six real sample questions passed again against the isolated current API: query totals in fixture order were **907.00, 1,671.30, 1,453.25, 936.09, 1,620.69 and 1,574.48 ms**. The unanswerable electricity-cost question had no citations. `scripts/verify_failure.py` also passed with real retrieval and TCP refusal. The updated existing API was restarted without changing its stored document/history rows; the two development-UI Chrome tests passed in **12.6 s**. The built cleanup checks above ran on a separate disposable API.

Aggregate GPU snapshots in this six-question run were GPU 0 **23,254 MiB / 0% → 23,282 MiB / 100%**, GPU 1 **36,188 MiB / 94% → 36,188 MiB / 0%**. They include concurrent work and do not isolate application allocation, peak utilization or inference cost.

The fourteen English/Traditional Chinese UI images and both covers were refreshed from the current interface. The screenshot helper now shares the complete public-workspace guard and waits for history rows before capturing them. The final captured English/Chinese query totals were **820.54 ms / 812.68 ms**. A fresh nine-step movie from application commit `7e16f9b` includes upload, live questions/citations/parsing/settings/refusal/history and actual PDF/history deletion in the disposable workspace. Its two real query totals were **889.23 / 846.33 ms**. Both normal-speed H.264 videos measure **84.708333 s**, **1440 × 1200**, with editable bilingual captions. Complete decoding and eleven scene frames per language were reviewed. Caption rendering added zero further queries. Current source/render receipts are committed; the v0.1.0 release retains the original preview footage.

## Limits and next milestone

Only this three-page native-text fixture and the explicit contract inputs were evaluated. Live vLLM/OpenAI service integration, an SSH client on another machine, scanned/image-only PDFs, large corpora, concurrent multi-user traffic, adversarial claim entailment, and production hardening remain unverified or outside scope. Source boxes are Docling item bounds rather than exact phrase spans. Citation membership cannot establish semantic correctness by itself. There is no distributed job queue or resumable parsing; interrupted jobs become actionable failures.

Suggested next milestone: a fixed evaluation dataset and before/after run comparison, with retrieval recall/answer correctness/faithfulness metrics, plus replaceable hybrid retrieval and reranking. Keep OCR/VLM, a diagnostic agent, and embedding tuning as later independent adapters.
