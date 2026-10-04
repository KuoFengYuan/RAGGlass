# Repository working agreement

**English** | [繁體中文](AGENTS.zh-TW.md)

RAGGlass is a local document RAG diagnostic workbench. Its motto is **See inside your RAG.** Preserve the path from the original PDF to parsed content, retrieved chunks, and answers. This agreement adapts the owner's [reference workflow](https://github.com/KuoFengYuan/arkit-3dgs-scanner/blob/main/AGENTS.md) to this repository.

## Delivery workflow

1. Inspect the working tree, running services, and applicable instructions. Preserve unrelated changes, existing models, and other GPU workloads. Fetch `origin` and start from updated `main` when a remote exists and the worktree can be switched safely.
2. Use a task branch with one case-sensitive prefix and a lowercase hyphenated description: `Feature/` for new capabilities, `Bugfix/` for fixes, or `Enhance/` for improvements. Do not use `codex/` or lowercase variants. For a new local repository, an initial governance commit on `main` is permitted before creating the task branch.
3. Complete the authorized implementation and both documentation languages. Do not stop at a plan or code examples. Keep changes scoped. Review the final diff for secrets, uploaded documents, model weights, generated caches, and build output.
4. Run `bash scripts/check.sh`. For parser, retrieval, model, citation, or PDF UI changes, also run the relevant real-stack and browser checks described in the README. Distinguish contract tests from real model evidence. Record only measured timings and GPU usage. Do not claim a test, PR, merge, or service restart occurred without verifying it.
5. Commit with a concrete English subject using `feat:`, `fix:`, `enhance:`, or `docs:`. When GitHub delivery is authorized and a remote is configured, push the task branch and open a PR targeting `main`. Describe final behavior, tradeoffs, validation, and limitations in English first, followed by a Traditional Chinese summary. Use `.github/pull_request_template.md`. Do not add AI attribution or an AI `Co-Authored-By` trailer.
6. Inspect mergeability, required checks, and reviews. Fix failures and rerun affected checks. Merge the verified head, normally by squash, only after required gates pass and merge is within the authorized scope. Preserve the PR number in the resulting commit subject, for example `enhance: show inline demos (#12)`. Include this suffix explicitly when supplying a custom merge subject, and verify it in `main` history after merging. Never push directly to remote `main`, bypass protections, disable checks, or use administrator override. Report an external blocking gate precisely and leave the PR intact.
7. After confirmed merge, delete only this task's remote/local branch, update `main` with fast-forward only, and prune stale tracking refs. Never delete unrelated or unmerged work. Report the PR URL, merge commit, verification, and final branch state.
8. A user's later instruction overrides the default. If the user says publishing is for later, finish and validate locally, prepare a PR description, and report that no remote PR exists. Do not create a GitHub repository or publish private/local artifacts by assumption.

## Project rules

- English primary documentation: `README.md` and `docs/NAME.md`; complete Traditional Chinese counterparts: `README.zh-TW.md` and `docs/NAME.zh-TW.md`. Link both directions and keep links within the same language.
- Functional changes update both READMEs' capabilities, walkthrough, architecture and limits together with both `docs/DEMO` guides and the relevant feature guides. Keep video descriptions/coverage current. Captions must describe the recorded frames; new video demonstrations require fresh footage and matching bilingual captions, receipts and published embed metadata. Until re-recording, label the actual recorded application commit and link instructions for uncovered controls. Keep historical release notes scoped to their released version.
- Progress and delivery reports to the owner use Traditional Chinese. The UI defaults to Traditional Chinese and offers a persistent English language switch. Machine identifiers remain independent of display language.
- Vue 3, TypeScript, Vite, PDF.js frontend; FastAPI backend; Docling PDF parsing; Qdrant vectors; SQLite and local files for metadata/history. Keep model HTTP services separate from the application.
- Pin direct dependencies and commit `uv.lock` and `frontend/package-lock.json`. Docker images require explicit versions. Install dependencies/caches within project environments; never upgrade system GPU drivers as part of application work.
- Bind application and Qdrant ports to loopback by default. Use SSH tunnels for remote preview. Keep `.env`, API keys, document uploads, runtime databases, logs, and model caches out of Git.
- Persist document ID/hash, chunk IDs, every source page, parser/chunk/embedding/retrieval/model settings, prompts, evidence, answers, and actual stage timings. Never fabricate coordinates; label missing coordinates. Source item boxes are not exact text spans.
- Accept only citations belonging to the current query's retrieved IDs. Resolve file/page links on the backend. Reject unknown IDs; refuse answers without evidence. Cite validity does not prove that a claim is entailed: document this limitation.
- Keep parser, embedder, retriever, and model adapters independent so OCR/VLM, hybrid search, reranking, quantitative evaluation, diagnostic agents, and embedding tuning can be added later.
- First release handles native-text PDFs. Clearly label fictional fixtures and mocked tests. The production path must use real embeddings and real model inference.

See [contributing](CONTRIBUTING.md) and the [milestone record](docs/MILESTONE.md).
