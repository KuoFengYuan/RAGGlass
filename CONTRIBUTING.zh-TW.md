# 貢獻流程

[English](CONTRIBUTING.md) | **繁體中文**

歡迎透過 issue 與 PR 貢獻 RAGGlass，專案採 [MIT 授權](LICENSE)，原創範例／產生程式則依[範例說明](examples/README.zh-TW.md)使用 CC0。沒有寫入權限時先 fork，在自己的 fork 建立任務分支，再對本 repository 的 `main` 開 PR。請提供已去除敏感內容的小型重現、預期行為與實際驗證結果。

先閱讀 [AGENTS.md](AGENTS.zh-TW.md)，依 [README](README.zh-TW.md) 設定環境。從更新的 `main` 建立 `Feature/lowercase-description`、`Bugfix/lowercase-description` 或 `Enhance/lowercase-description` 分支，保留現有變更與服務。

提交前執行 `bash scripts/check.sh`。涉及 pipeline 或介面時，啟動真實服務後執行 `.venv/bin/python scripts/verify_e2e.py`，再執行 `npm --prefix frontend run test:e2e`。瀏覽器測試使用真實模型與 CC0 範例，需要本機 Google Chrome，或依 README 安裝的 Playwright 瀏覽器。只記錄實測結果，測試報告及執行資料不得進 Git。

提交標題用具體英文，不加 AI 工具歸屬。依雙語模板對 `main` 開 PR，等待必要檢查與審查，不繞過保護。合併／squash 提交標題須以 PR 編號結尾，例如 `enhance: show inline demos (#12)`，讓 GitHub 提交歷史能連回 PR。自訂 merge subject 時加入後綴，合併後查證已發布的提交。確認合併（通常採 squash）後，只移除此任務已合併分支，以 fast-forward 更新本機 `main`，並回報 PR 與 merge commit。GitHub 發布必須符合使用者授權範圍；無 remote 的本機 repository 仍可完成實作、測試與提交。

第一里程碑範圍：原生文字 PDF、向量檢索與獨立 HTTP 模型。擴充透過獨立 adapter 實作。已有服務能滿足任務時不另啟模型伺服器；不可混用 embedding 空間、虛構座標、接受未驗證引用，或以固定答案代替即時推論。
