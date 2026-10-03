# Contributing

**English** | [繁體中文](CONTRIBUTING.zh-TW.md)

RAGGlass welcomes issues and pull requests under the [MIT License](LICENSE); the original fixture/generator use CC0 as documented in [examples](examples/README.md). Fork the repository if you do not have write access, create a task branch in your fork, and open a PR against this repository’s `main`. Provide a small sanitized reproduction, expected behavior, and actual validation results.

Read [AGENTS.md](AGENTS.md), then follow the setup in [README.md](README.md). Use `Feature/lowercase-description`, `Bugfix/lowercase-description`, or `Enhance/lowercase-description` branches based on updated `main`. Preserve existing changes and services.

Run `bash scripts/check.sh` before committing. For pipeline/UI changes, start the real stack, run `.venv/bin/python scripts/verify_e2e.py`, then `npm --prefix frontend run test:e2e`. The browser test uses the real model and the CC0 fixture. It requires local Google Chrome, or a Playwright browser installed as documented in the README. Capture only measured results. Keep test reports and runtime data out of Git.

Commit with a concrete English subject, without AI tool attribution. Open a PR to `main` using the bilingual template. Wait for required checks and reviews; do not bypass protections. After a confirmed merge (normally squash), remove only the merged task branch, fast-forward local `main`, and report the PR and merge commit. GitHub publication happens only within the user's authorized delivery scope. A local repository without a remote can still be implemented, tested, and committed.

First-milestone scope: native-text PDFs, dense retrieval, and independent HTTP models. Keep extension work isolated behind adapters. Do not add a second model server when an existing service satisfies the task, silently change embedding spaces, invent coordinates, accept unvalidated citations, or substitute canned responses for live inference.
