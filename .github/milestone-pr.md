## Change

Deliver the first executable RAGGlass workbench. Engineers can upload a native-text PDF, inspect the original and parsed content, ask a real model, and follow validated retrieved chunk citations to original source pages. SQLite, local files, and persistent Qdrant preserve documents, evidence, prompts/settings, answers, errors, and measured timings after restarts.

The document inspection interface uses a horizontal masthead, PDF page rail, adjacent answer/evidence inspector, document/history dialogs, and a measured execution trace. It defaults to Traditional Chinese with a persistent English switch and stacks vertically on narrow screens. English-first bilingual READMEs document setup, sample questions, model recommendations, exact Ollama names, and reproduction steps. `gemma4:e4b` is the real-tested baseline; Qwen3.8-27B and Gemma4-31B are explicitly untested comparison candidates. Future Ollama embedding choices are clearly separated from answer models and require an adapter/reindexing.

Includes independent FastAPI parser/embedding/retrieval/model adapters, pinned uv/npm dependencies, loopback Qdrant v1.15.5 Compose, a publishable three-page CC0 fixture, six questions, bilingual AGENTS/contribution rules, CI, and measured milestone evidence. Existing model services and other GPU workloads are preserved.

The owner authorized a public open-source release. Application code/documentation use the MIT License; the original fixture/generator keep CC0. Both READMEs and contributing guides explain the licenses and external contribution workflow.

The illustrated English/Traditional Chinese usage and deployment guides cover the complete workflow, setup, independent model service, startup modes, optional systemd user unit, SSH, persistence/backup, updates, and troubleshooting. Ten actual bilingual screens were captured through live sample inference. A capture helper restricts publication to the fixture-only workspace. The README front page explains the purpose, current capabilities, quick-start/documentation links, and Star entry.

## Validation

- [x] `bash scripts/check.sh`: Ruff lint/format, **11 passing contract/API tests**, Prettier, TypeScript/Vite, bilingual delivery-file checks.
- [x] `.venv/bin/python scripts/verify_e2e.py`: **6 real-model questions passed**, known evidence/page mappings and citation membership checked; insufficient evidence refuses without citations. Latest total query times: 772.06, 1,166.68, 815.05, 924.18, 818.73, 838.34 ms.
- [x] `npm --prefix frontend run test:e2e`: **2 real Chrome tests passed**, 6.4 s.
- [x] `RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e`: **2 real Chrome tests passed**, 4.9 s. Includes live answer, PDF/page highlight, parsed chunks, history, bilingual persistence, document catalog, Escape/focus restoration, invalid retrieval input, and resized 390-pixel mobile layout.
- [x] Initial milestone also verified actual API/Qdrant restart persistence, a Chinese question against the English PDF, and real retrieval with an unreachable model endpoint (`verify_restart.py`, `verify_failure.py`; see the bilingual milestone record). These disruptive checks were not repeated for the UI/docs-only update.
- [x] Both documentation languages updated with official model sources checked on 2026-10-03. `node scripts/capture_ui_docs.mjs` captured ten actual bilingual views using two live queries; `systemd-analyze --user verify deploy/ragglass.service` passed. The user service was not activated and full backup/restore was not executed.
- [x] Working changes and local Git history checked for secrets, private uploads, caches, model weights, and build output. Only the original public fixture and its selected UI screenshot are included.

Contract inputs and the OpenAI HTTP fixture are explicitly synthetic. The sample facts are fictional; native Ollama inference, PDF rendering, retrieval, and the recorded UI screenshot are real. GPU snapshots include other workloads; no peak memory or candidate-model benchmark is claimed. Hosted CI runs contracts/build/docs; real model evidence comes from the local stack.

## Limits and tradeoffs

Native-text PDFs only. Single-user loopback service with serialized ingestion and no authentication/distributed jobs. Docling coordinates identify source items, not exact text spans. Citation membership does not prove semantic entailment. Live vLLM, remote-client SSH, large corpora, adversarial faithfulness, and all recommended replacement models remain unverified. The first publication preserves the local governance/implementation ancestry; subsequent PRs can use the normal squash workflow.

Next milestone: fixed bilingual evaluation sets and before/after run comparisons, then replaceable hybrid retrieval and reranking. Embedding migration requires a separate evaluated adapter, fresh vectors, and calibrated thresholds.

## 繁體中文摘要

依使用者要求公開為開源專案：程式／文件採 MIT，原創範例／產生程式維持 CC0，兩種語言皆提供授權與外部貢獻方式。

首次交付可執行的 RAGGlass：PDF 上傳／解析／索引、真實模型問答、後端驗證引用跳原頁，以及可持久重開的文件／執行紀錄。版面改為頂部導覽、原始文件閱讀區與答案／證據檢視面板，提供文件庫、歷史對話框與手機垂直配置。

中英文 README 已加入 Ollama 模型用途、取捨、確切名稱、切換與重現步驟；E4B 是已實測預設，Qwen3.8-27B／Gemma4-31B 是未評測候選，embedding 選項尚須獨立整合。11 個契約測試、六題真實模型，以及開發／正式版各兩個瀏覽器測試均通過。初始里程碑亦已實測重啟持久化、中文查詢及模型不可連線錯誤。未下載其他模型、修改驅動或停止共用服務；OCR、混合檢索、reranker、正式品質評測及大型資料驗證仍待後續里程碑。
