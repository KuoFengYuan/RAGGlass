# Repository 工作約定

[English](AGENTS.md) | **繁體中文**

RAGGlass 是地端文件 RAG 診斷工作台，標語為 **See inside your RAG.** 保留原始 PDF、解析內容、檢索片段到回答的完整追查路徑。本約定參考專案擁有者的[既有流程](https://github.com/KuoFengYuan/arkit-3dgs-scanner/blob/main/AGENTS.md)，調整為本專案適用規則。

## 交付流程

1. 檢查工作樹、運行中的服務與適用規則。保留不相關變更、既有模型及其他 GPU 工作。有 remote 且可安全切換時，fetch `origin` 並從更新後的 `main` 開始。
2. 任務分支採大小寫敏感前綴與小寫連字號描述：新功能用 `Feature/`、修正用 `Bugfix/`、改善用 `Enhance/`。不可用 `codex/` 或前綴的小寫變體。全新本機 repository 可先在 `main` 建立治理文件的初始提交，再建立任務分支。
3. 完成已授權的實作與兩種語言文件，不停在計畫或程式範例。檢查最終 diff，排除敏感資料、上傳文件、模型權重、快取與建置產物。
4. 執行 `bash scripts/check.sh`。涉及解析、檢索、模型、引用或 PDF 介面時，再執行 README 所述的相關真實流程與瀏覽器驗證。區分契約測試與真實模型證據，耗時與 GPU 數值只記錄實測。未查證不可宣稱測試、PR、合併或服務重啟已完成。
5. 提交使用具體英文標題與 `feat:`、`fix:`、`enhance:` 或 `docs:` 前綴。已授權 GitHub 交付且有 remote 時，推送任務分支並向 `main` 開 PR。依 `.github/pull_request_template.md`，先以英文說明最終行為、取捨、驗證及限制，再附繁體中文摘要。不可加入 AI 工具歸屬或 AI `Co-Authored-By` trailer。
6. 檢查可合併性、必要檢查與審查。修正失敗並重跑相關驗證。必要 gate 全部通過、且合併在授權範圍內後，才合併已驗證的 head，通常使用 squash。合併提交標題保留 PR 編號，例如 `enhance: show inline demos (#12)`。自訂 merge subject 時必須明確加入此後綴，合併後從 `main` 歷史確認。不可直接推送 remote `main`、略過保護、停用檢查或使用管理員繞過。遇到外部 gate，明確說明阻礙並保留 PR。
7. 確认合併後，只刪除此任務遠端／本機分支，以 fast-forward 更新 `main` 並清理過期追蹤參照。不可刪除不相關或尚未合併的工作。回報 PR 網址、merge commit、驗證與最終分支狀態。
8. 使用者較新的指示優先。如果使用者表示稍後才發布，先完成本機驗證、準備 PR 說明，並回報尚無遠端 PR。不可自行建立 GitHub repository 或發布本機／私人產物。

## 專案規則

- 文件以英文優先：`README.md` 與 `docs/NAME.md`；提供完整繁體中文版本 `README.zh-TW.md` 與 `docs/NAME.zh-TW.md`。雙向連結，並在同語言文件內連結。
- 功能變更需同步更新中英文 README 的功能、操作流程、架構與限制，以及兩份 `docs/DEMO` 和相關功能指南。影片描述／涵蓋範圍需跟上更新。字幕必須對應錄影畫面；要在影片展示新功能，需重新錄製並同步雙語字幕、來源紀錄與已發布嵌入 metadata。重新錄製前，標示實際錄製的應用提交，連結尚未拍入功能的操作說明。歷史版本說明維持該次發布範圍。
- 向擁有者的進度及交付報告用繁體中文。介面預設繁體中文，提供可持久保存的英文切換。機器識別碼獨立於顯示語言。
- 前端 Vue 3、TypeScript、Vite、PDF.js；後端 FastAPI；Docling 解析；Qdrant 向量；SQLite 與本機檔案保存紀錄。模型 HTTP 服務與應用分開。
- 固定直接依賴並提交 `uv.lock`、`frontend/package-lock.json`。容器映像使用明確版本。依賴與快取在專案環境內；不可為應用開發升級系統 GPU 驅動。
- 應用與 Qdrant 預設只綁 loopback，以 SSH tunnel 遠端預覽。`.env`、API key、上傳文件、資料庫、日誌與模型快取不得進 Git。
- 保存文件 ID/hash、chunk ID、所有來源頁碼、解析／切塊／embedding／檢索／模型設定、prompt、證據、答案及實際階段耗時。不可虛構座標，缺失時標示。來源內容區塊框線不是精確文字範圍。
- 只接受本次檢索 ID 的引用，由後端解析文件／頁碼；拒絕不存在的 ID，證據不足則不回答。引用存在不代表答案語意必然受到支持，須揭露此限制。
- 解析、embedding、retriever、模型 adapter 獨立，以便擴充 OCR/VLM、混合檢索、reranker、量化評測、診斷 Agent 與 embedding 微調。
- 第一版只處理原生文字 PDF。虛構範例與 mock 測試須清楚標示。正式路徑使用真實 embedding 與模型推論。

請參閱[貢獻流程](CONTRIBUTING.zh-TW.md)與[里程碑紀錄](docs/MILESTONE.zh-TW.md)。
