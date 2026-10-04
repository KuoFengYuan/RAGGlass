# Contributing

**English** | [繁體中文](CONTRIBUTING.zh-TW.md)

RAGGlass welcomes issues and pull requests under the [MIT License](LICENSE); the original fixture/generator use CC0 as documented in [examples](examples/README.md). Fork the repository if you do not have write access, create a task branch in your fork, and open a PR against this repository’s `main`. Provide a small sanitized reproduction, expected behavior, and actual validation results.

Read [AGENTS.md](AGENTS.md), then follow the setup in [README.md](README.md). Use `Feature/lowercase-description`, `Bugfix/lowercase-description`, or `Enhance/lowercase-description` branches based on updated `main`. Preserve existing changes and services.

Update both READMEs and the [video/current-controls guide](docs/DEMO.md) with every functional change, including capabilities, steps, architecture, limits and the relevant bilingual feature guides. Check that video descriptions say what the published footage actually covers. Keep its recorded commit explicit and provide instructions for controls absent from the video. Captions must match the frames; showing a new control requires fresh footage and synchronized bilingual subtitles, receipts and verified embeds. Historical release notes continue to describe their own version. Include this documentation/media check in the PR validation.

Run `bash scripts/check.sh` before committing. For pipeline/UI changes, start the real stack, run `.venv/bin/python scripts/verify_e2e.py`, then `npm --prefix frontend run test:e2e`. The browser test uses the real model and the CC0 fixture. It requires local Google Chrome, or a Playwright browser installed as documented in the README. Capture only measured results. Keep test reports and runtime data out of Git.

Commit with a concrete English subject, without AI tool attribution. Open a PR to `main` using the bilingual template. Wait for required checks and reviews; do not bypass protections. The merge/squash commit subject must end with the PR number, for example `enhance: show inline demos (#12)`, so GitHub's commit history links back to the PR. Include the suffix when overriding the merge subject and check the published commit afterward. After a confirmed merge (normally squash), remove only the merged task branch, fast-forward local `main`, and report the PR and merge commit. GitHub publication happens only within the user's authorized delivery scope. A local repository without a remote can still be implemented, tested, and committed.

First-milestone scope: native-text PDFs, dense retrieval, and independent HTTP models. Keep extension work isolated behind adapters. Do not add a second model server when an existing service satisfies the task, silently change embedding spaces, invent coordinates, accept unvalidated citations, or substitute canned responses for live inference.
