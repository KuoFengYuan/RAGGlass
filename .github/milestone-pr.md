# feat: add the first executable RAGGlass workbench

## Change

Engineers can upload a native-text PDF, inspect the original with PDF.js and the Docling output, ask a question, and trace a real model answer back to retrieved chunk IDs and source pages. The backend rejects citations outside the current evidence. Original files, chunks, document metadata, exact query settings/prompts, evidence, answers, errors, and measured timings survive service restarts through SQLite, local files, and persistent Qdrant storage.

The Vue 3/TypeScript UI defaults to Traditional Chinese and offers persistent English selection. Independent CPU Docling/E5 adapters and configurable Ollama/OpenAI-compatible HTTP model clients leave clear interfaces for hybrid retrieval, reranking, OCR/VLM, evaluation, and embedding tuning. The app reuses the existing local Ollama `gemma4:e4b`; no second model service or driver upgrade is introduced.

Includes English-first bilingual README/AGENTS/contribution docs, pinned Python/npm dependencies, loopback Qdrant v1.15.5 Compose, local/SSH preview instructions, a three-page original CC0 PDF, six verification questions, CI checks, and a measured milestone report.

## Validation

- `bash scripts/check.sh`: Ruff lint/format, Prettier, 11 passing contract/API tests, TypeScript and Vite build, bilingual delivery-file checks.
- `npm --prefix frontend audit --audit-level=high`: 0 reported vulnerabilities.
- `.venv/bin/python scripts/verify_e2e.py`: real Docling/E5/Qdrant/Ollama, all six questions passed, including no evidence for electricity cost. Verified page mapping, known evidence, and citation membership. First successful ingest: 36.15 s including model initialization/downloads; first query: 7.45 s; subsequent five: 0.81–1.04 s.
- `npm --prefix frontend run test:e2e`: real Chrome upload/question/source-page/history/language test passed.
- The default Traditional Chinese question retrieved the English PDF and returned 30 MB with a page-2 citation (1,001.11 ms).
- `.venv/bin/python scripts/verify_failure.py`: real retrieval with unreachable LLM preserves failed-run evidence and a clear actionable error.
- `.venv/bin/python scripts/verify_restart.py --api-pid <verified-project-pid>`: actual API/Qdrant restart preserved the document, seven existing runs, and six vectors; a fresh real answer cited page 2. Built UI returned HTTP 200.

The OpenAI adapter HTTP test uses an explicitly synthetic fixture. Native Ollama inference and all displayed fixture answers are live, not precomputed. GPU snapshots include unrelated concurrent work and are not attributed solely to this application.

## Limits and tradeoffs

Native-text PDFs only. Single-user loopback workbench, serialized background ingestion, no distributed job queue/authentication. Source coordinates represent Docling item bounds. Citation validity does not prove claim entailment. Live vLLM, a remote SSH client, large corpora, and adversarial faithfulness remain unverified. Suggested next milestone: fixed evaluation sets and before/after comparisons with hybrid retrieval/reranking adapters.

## 繁體中文摘要

完成可實際操作的 RAGGlass 第一里程碑：上傳 PDF、查看解析與原始文件、真實模型問答、引用跳頁、設定／耗時與歷史紀錄。引用由後端限制為當次檢索 chunk ID，文件、證據與 run 透過 SQLite、本機檔案與 Qdrant 持久保存。

11 個契約／API 測試、六題真實模型、Chrome 瀏覽器、模型無法連線與實際 API／Qdrant 重啟驗證通過；TypeScript／Vite 建置與雙語交付檢查通過。保留既有服務，採 CPU 解析／embedding 與獨立 Ollama 模型 API。尚未支援 OCR、混合檢索、reranker 或正式量化評測；未實測遠端 vLLM、SSH 客戶端、大型 corpus 與對抗性語意支持。

This is a ready-to-use PR body, not evidence that a remote PR has been created. GitHub publication was requested for later.
