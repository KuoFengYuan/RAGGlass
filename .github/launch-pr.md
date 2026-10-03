## Change

Give the first RAGGlass release a reproducible way to explain its PDF/evidence/answer workflow. The README now leads with an actual citation interaction GIF and links to a full live-model recording. English and Traditional Chinese versions include captioned videos, GIFs, 1280 × 640 share covers, technical announcement drafts, a table/source case study, launch/traffic guidance, and first-preview release notes.

`capture_demo.mjs` exercises the actual local UI and model, preserves a public recording receipt, and exports videos/subtitles to ignored local storage for release attachments. Publication guards require an indexed fixture-only workspace and reject private questions/documents, truncated history, non-loopback services, and model URL credentials. Captions occupy a separate strip below the UI; playback stays at normal speed. The sample's existing index is explicitly reused.

`record_traffic.py` reads GitHub's actual metrics into ignored local snapshots with no posting/repository mutations. Missing metrics stay unavailable. The guide explains overlapping 14-day windows, sources, a suggested first week, and personal community participation. Social preview covers are prepared assets: GitHub's documented settings upload remains a manual step. The v0.1.0 release will attach the verified MP4/subtitle files after merge.

## Validation

- [x] `bash scripts/check.sh`: Ruff, **11 Python contract/API tests**, frontend Prettier, TypeScript/Vite build, all script syntax, **7 synthetic publication-guard contracts**, bilingual links/files, PNG dimensions/size, and GIF checks passed.
- [x] `node scripts/capture_demo.mjs`: two actual `gemma4:e4b` queries; 30 MB with retrieved citation/page 2, source boxes, parsed table, settings, unsupported-question refusal without citations, saved history, and no browser errors. Latest query totals **5,177.93 ms / 898.10 ms**; first request includes Ollama-reported **4,626.75 ms** model loading. Actual MP4 duration **54.791667 s**, 1440 × 1000, H.264/yuv420p. No GPU benchmark or fresh ingestion measurement.
- [x] `node scripts/render_social_preview.mjs`: both real-interface covers rendered at 1280 × 640, under 1 MB; images reviewed.
- [x] FFmpeg decoded both MP4 files without errors; English/Chinese frames/captions reviewed. Actual public-workspace preflight passed. Published case/milestone totals checked against the recording receipt.
- [x] `.venv/bin/python scripts/record_traffic.py --note ...`: actual GitHub baseline fetched and saved locally. No exposure/star growth claimed.
- [x] Both documentation languages completed. Diff audited for secrets, private uploads, raw footage, dependencies, model weights, caches, and build output.

The seven new preflight tests use explicitly synthetic HTTP responses and test publication boundaries; they do not simulate model inference. Videos use the original fictional CC0 fixture, real embeddings/retrieval/model inference, and actual PDF UI interaction. Full-stack restart/model-failure evidence remains in the prior milestone; application code and shared services are unchanged.

## Limits and tradeoffs

This adds launch materials and reproduction helpers, without expanding the first release's native-text/single-user scope. Citation membership does not prove semantic entailment. Large corpora, OCR, vLLM, alternate model quality, and quantitative before/after comparisons remain unverified or future work. GitHub Social preview upload and personal social/community posting are manual; no posts or recurring automations were sent. The capture tool needs the local real stack, Chrome/Chromium, FFmpeg, and a CJK font. Raw media and owner analytics remain ignored; only selected public assets and recording metadata enter Git.

## 繁體中文摘要

加入完整中英文曝光素材：README 真實引用操作 GIF、約 55 秒中英字幕影片、1280 × 640 封面、技術貼文、表格來源案例、分享／流量指南與首次版本說明。v0.1.0 影片／字幕在驗證合併後作為 Release 附件發布。

本機完整檢查通過 11 個 Python 測試、7 個合成的公開錄製邊界測試、前端建置與雙語／素材檢查。最終錄製兩題真實模型耗時 5,177.93／898.10 ms，第一題包含模型載入；確認引用回第 2 頁、解析、設定、拒答與歷史，兩支影片均可解碼，字幕／封面已檢查。

流量工具唯讀取得實際 GitHub 基準，保存在本機；不宣稱曝光成效。共用服務與模型保留。Social preview 圖片仍需 GitHub 網頁上傳，社群文案提供作者自行發布，沒有自動發文或排程。原始錄影、私人資料、憑證、快取與分析快照不進 Git。
