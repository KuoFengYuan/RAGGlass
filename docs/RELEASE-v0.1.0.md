# RAGGlass v0.1.0 — native-text PDF preview

**English** | [繁體中文](RELEASE-v0.1.0.zh-TW.md)

**See inside your RAG.** Inspect an original PDF beside retrieved evidence and a real model answer, then follow its citations back to source pages. This first public preview is MIT-licensed, runs locally, and includes complete English/Traditional Chinese guides.

## Try this version

Use the [README](../README.md), [illustrated usage](USAGE.md), and [deployment guide](DEPLOYMENT.md). Required: Linux, Python 3.12, Node 20.19+, Docker Compose, and a reachable Ollama or OpenAI-compatible HTTP model service. Default answer model `gemma4:e4b` was tested with real inference; parsing/embedding use CPU and Qdrant runs through the pinned Compose configuration. Initial dependency/model downloads require internet access.

[Watch the demo with English captions](https://github.com/KuoFengYuan/RAGGlass/releases/download/v0.1.0/ragglass-demo.mp4) · [Try the CC0 PDF](../examples/ragglass-field-guide.pdf) · [Six sample questions](../examples/questions.json)

## Included

- Upload/index native-text PDFs with Docling and inspect original PDFs through PDF.js.
- Retrieve real multilingual E5 embeddings through Qdrant and generate answers through a separate model HTTP service.
- Accept only citations belonging to this query's retrieved IDs and resolve them to original files/pages.
- Inspect parser output, source coordinates when available, scores, prompts, settings, model metadata, and measured stage timings.
- Persist documents and history in SQLite/local files and Qdrant storage.
- Use a responsive document workbench with Traditional Chinese as default and a persistent English switch.
- Reproduce setup with locked uv/npm dependencies, loopback defaults, and an SSH-tunnel guide.
- Share a recorded live-model demo, bilingual covers, a source-tracing case study, and prepared technical post drafts.

## Verification

The initial milestone passed **11 contract/API tests**, six real-model questions, browser checks on development and built interfaces, actual API/Qdrant restart persistence, and the unreachable-model error flow. The [milestone record](MILESTONE.md) distinguishes synthetic contract inputs from the real stack and records actual measurements.

The launch recording makes two new live queries and checks the known table answer, retrieved citation membership, PDF page 2/source boxes, parsed table, settings, unsupported-question refusal, saved history, and absence of browser errors. The videos use the same English interface recording, with English or Traditional Chinese captions below the UI. They play at normal speed and reuse the sample's existing index. [Recording receipt](media/demo-recording.json)

Media render checks, the full `bash scripts/check.sh`, and the publishing PR's CI are recorded in the PR. Raw recordings, dependencies, caches, private uploads, keys, and local traffic snapshots are excluded from Git. MP4s and subtitle files are release attachments.

## Scope and next step

This is a single-user preview bound to loopback with no authentication. Native-text PDFs only. OCR/VLM, hybrid retrieval, reranking, automated diagnosis, formal quality scoring, and before/after run comparisons are not included. Citation membership is not semantic entailment, and source boxes are not exact phrase spans. Other model recommendations are candidates, not measured quality rankings. Live vLLM, remote SSH clients, large corpora, and optional systemd/backup workflows remain unverified as detailed in the deployment/milestone guides.

The next milestone should establish a fixed bilingual evaluation set and reproducible before/after run comparisons, followed by replaceable hybrid retrieval and reranking.

Issues and PRs are welcome through the [contribution workflow](../CONTRIBUTING.md). Reproductions should use public/sanitized documents. Application code/docs use [MIT](../LICENSE); the original fixture/generator use CC0, and third-party dependencies/models retain their own licenses.
