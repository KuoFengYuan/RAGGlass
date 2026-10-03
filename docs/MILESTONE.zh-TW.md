# 第一里程碑：可執行的文件 RAG 工作台

[English](MILESTONE.md) | **繁體中文**

驗證日期：**2026-10-03**，Asia/Taipei。初始目錄為空，沒有 Git 或 AGENTS.md。目前已建立 Vue／PDF.js 工作台、FastAPI 應用、獨立解析／embedding／檢索／模型 adapter、本機持久化、依賴鎖定、Qdrant Compose 儲存、CC0 範例、自動檢查與雙語貢獻規範。

## 實測環境與選擇

| 項目 | 實測結果 |
| --- | --- |
| OS | Ubuntu 24.04.4 LTS，Linux 6.17.0-1023-oem，x86_64 |
| GPU | 2 × NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition |
| 顯存 | nvidia-smi 回報每張 97,887 MiB |
| 驅動 | 595.71.05；nvidia-smi 顯示 CUDA 相容版本 13.2 |
| 初始 GPU 工作 | GPU 0 使用 895 MiB，其中既有 Python 占 856 MiB；GPU 1 使用 156 MiB。當下兩張利用率皆為 0%。 |
| RAM | 總計 502 GiB，初始可用 480 GiB |
| 磁碟 | 初始工作目錄所在檔案系統可用 1.6 TB |
| Python | 預設 3.13.12；專案使用既有 `/usr/bin/python3.12`，版本 3.12.3 |
| Node/npm | 20.20.2 / 10.8.2 |
| Docker/Compose | 29.3.0 / v5.1.0 |
| 重用模型服務 | 已存在的 loopback Ollama，port 11434，模型 `gemma4:e4b` |

未更動驅動、既有容器或不相關服務。系統 Python 3.12 缺少 ensurepip，透過專案內 uv 成功建立 `.venv`。Torch 2.8.0 使用 CPU wheel，四個 CPU 執行緒，以及固定的 `intfloat/multilingual-e5-small` revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`，避免 CUDA 套件相容性與解析／embedding 額外 GPU 使用。Docling 2.60.1 在 CPU 解析原生文字 layout／表格，關閉 OCR。Qdrant 固定為 `v1.15.5`，Vite 固定為 `7.3.6`；替換初選舊版本後，`npm audit --audit-level=high` 回報 **0 個漏洞**。

## 真實 PDF 與模型驗證

`scripts/verify_e2e.py` 使用真實 API、Docling、E5、Docker Qdrant 與既有 Ollama，沒有 mock 回答或 embedding。原創三頁範例描述虛構事實與配額，不是假稱的部署量測。

- 文件 SHA-256：`878bfa94da33d16c947f174d12560e3f7b4efa807cbd0b189f0841af7db58d8a`。
- 解析 **3 頁**，索引 **6 個 chunks**；全部保留文件 hash、有效來源頁碼與可用原始座標。
- 對照實際 PDF 文字，驗證第 1 頁負責人、第 2 頁表格證據。
- 所有回答引用均屬於當次檢索 chunk ID，且對應實際上傳文件與預期頁碼。
- 保存確切 prompt、證據、模型選項、tokenizer／切塊／檢索設定、原始模型回覆、服務 metadata 與實測耗時。

首次成功處理包含模型下載與初始化：

| 階段 | 實測耗時 |
| --- | ---: |
| Docling 解析 | 21,886.26 ms |
| Tokenizer 初始化與切塊 | 13,990.88 ms |
| 片段 embedding | 123.00 ms |
| Qdrant 索引 | 142.75 ms |
| 整體處理 | 36,151.55 ms |

切塊階段包含首次 embedding 模型／tokenizer 載入；以上為該次 wall-clock 實測，不是純 tokenizer benchmark。

| 真實模型問題 | 驗證結果 | 整體耗時 |
| --- | --- | ---: |
| 上傳容量上限？ | 30 MB，第 2 頁 | 7,446.41 ms |
| Chunk overlap？ | 32 tokens，第 2 頁 | 877.70 ms |
| 誰維護計畫？ | Mira Chen，第 1 頁 | 809.50 ms |
| 是否支援 OCR？ | 關閉，第 1 頁 | 990.36 ms |
| Metadata／紀錄存在哪裡？ | SQLite，第 1 頁 | 1,044.51 ms |
| 年度電費？ | 無法確認，沒有引用 | 856.21 ms |

首次回答生成階段為 7,425.12 ms，其中模型服務回報載入時間 6,860.39 ms。後續查詢 embedding 為 10.48–14.20 ms、檢索 4.79–6.44 ms、生成 791.22–1,025.62 ms。這是小型 PDF 的六個實測樣本，不是正式 benchmark。

問答期間 GPU 快照：

| 快照 | GPU 0 | GPU 1 |
| --- | --- | --- |
| 六題之前 | 使用 6,239 MiB；利用率 0% | 使用 36,906 MiB；利用率 86% |
| 六題之後 | 使用 11,284 MiB；利用率 91% | 使用 36,906 MiB；利用率 0% |

以上為整體瞬間快照，包含同時進行的其他工作。Ollama 當時也回報其他活動載入的 `Qwen3.8:27b`，已保持運行。不能將整體顯存差異全部歸因於 RAGGlass。`gemma4:e4b` 在 context 8192 時由 Ollama 回報 `size_vram=3367921253` bytes（**3.1366 GiB**），模型 digest 為 `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb`。這是服務回報值，不是隔離後的顯存 benchmark。

## 其他驗證

- **11 個契約／API 測試通過**：引用精確映射、無效 ID、沒有引用的主張拒答、錯誤 JSON、實際 TCP 拒絕連線、SQLite 重開、中斷復原、敏感資訊排除、合成 OpenAI HTTP 格式、無效／加密上傳、不存在文件／空問題。OpenAI HTTP fixture 明確採合成資料，原生 Ollama 端到端則是真實模型。
- **1 個 Chrome 瀏覽器測試通過**：實際上傳、真實模型問答、引用跳第 2 頁、座標框線、重新整理後紀錄、解析片段與持久語言偏好，該次完成時間為 **7.8 秒**。
- `scripts/verify_failure.py` 以真實 E5／Qdrant 檢索及不可連線 LLM endpoint 通過驗證。API 提供可處理的 `llm_unavailable` 紀錄，SQLite 保留證據／prompt／耗時並可查閱失敗 run，未停止共用模型服務。
- 預設繁體中文問題也已對英文 PDF 實測：`Cedar 試用方案的上傳容量上限是多少？` 得到 `Cedar 試用方案的每份 PDF 文件最大上傳大小限制為 30 MB。`，引用第 2 頁，耗時 **1,001.11 ms**。額外紀錄保存在 `.data/chinese-verification.json`。
- 最終格式整理與實際服務重啟後，Chrome 開發介面測試再次通過，耗時 **3.8 秒**。FastAPI 正式建置介面另以 `RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e` 驗證。
- TypeScript 與 Vite 正式建置通過，Ruff lint／format、Prettier 通過。`bash scripts/check.sh` 全部通過，`git diff --cached --check` 通過。本機實測紀錄與瀏覽器截圖保存在 Git 忽略的 `.data/`。

## 文件檢視版面與模型建議

後續改版以頂部導覽及文件／紀錄對話框取代常駐側欄。原始 PDF 為主要閱讀區，提供頁碼列與解析內容頁籤；相鄰檢視面板呈現問題、答案、已驗證來源連結與可展開檢索片段，底部顯示實測階段耗時。紙張色／炭灰／赭紅版面與稜鏡標記皆使用本機 CSS／SVG，無外部字型或圖片服務；保留繁體中文預設與持久英文切換。空白或超出範圍的檢索參數會阻止提交，鍵盤快捷鍵亦適用。

改版後於 **2026-10-03** 驗證：

- `bash scripts/check.sh` 通過：**11 個契約／API 測試**、Ruff、Prettier、TypeScript、Vite 與雙語文件。
- **兩個 Chrome 測試在兩種介面皆通過**：開發版（`npm --prefix frontend run test:e2e`，**6.4 秒**）及 FastAPI 正式建置介面（`RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e`，**4.9 秒**）。涵蓋真實推論、引用跳頁／標示、歷史重開、解析內容、語言偏好、文件庫、Escape 關閉與焦點恢復、無效檢索輸入，以及 390 × 844 視窗的 PDF 重新縮放和整體頁面無水平溢出。
- `.venv/bin/python scripts/verify_e2e.py` 再次通過全部**六題真實模型問題**。依範例順序總查詢耗時為 **772.06、1,166.68、815.05、924.18、818.73、838.34 ms**。本次上傳重用既有範例索引，未重新量測文件處理；電費題拒答且無引用。
- 該次前後快照皆為 GPU 0 **11,284 MiB／0%**、GPU 1 **36,906 MiB／95%**。這是包含其他工作的整體快照，不能當作應用峰值顯存。
- README 圖片源自正式建置介面的實際執行，內容僅含可散布的虛構範例；本機截圖／報告留在 `.data`，只有選定的文件展示圖片提交 Git。

兩份 README 現在都包含回答模型建議、本機與 registry 的確切名稱、切換／重現步驟，以及後續 Ollama embedding 候選，官方來源於同日核對。`gemma4:e4b` 保留為已量測預設；已安裝的 `Qwen3.8:27b` 與 `gemma4:31b` 是待比較候選，`gemma4:12b` 與 Ollama embedding 尚未測試。本次未下載、替換或評測其他候選，未將建議寫成已證明更好，並保留共用模型服務與其他 GPU 工作。

## 持久化與交付

SQLite 重開契約已通過，隨後 `scripts/verify_restart.py --api-pid 2758755` 實際只停止已確認屬於本專案的 API、重啟本專案 Qdrant 容器，再啟動新 API。**上傳文件與原有七筆紀錄完整保留，Qdrant 六個 points 也全數保留。** 重啟後再次詢問真實模型，回覆 **30 MB** 且引用第 2 頁；port 8000 的正式建置介面回傳 HTTP 200。新 API PID 為 2769439。PID 僅用來識別本次執行，不可拿來重啟之後的服務。

重現真實流程可執行 `.venv/bin/python scripts/verify_e2e.py`、`.venv/bin/python scripts/verify_failure.py`；Linux 上使用當前實際 API PID 執行 `.venv/bin/python scripts/verify_restart.py --api-pid PID`。最後一項會重啟 API 與本專案 Qdrant，發送訊號前先確認程序歸屬。日誌與機器可讀紀錄位於 `.data/backend.log`、`.data/verification.json`、`.data/failure-verification.json`、`.data/restart-verification.json`。`npm --prefix frontend run test:e2e` 產生本機截圖 `.data/workbench.png`。

本機 Git 流程：先在 `main` 建立治理初始提交，實作於 `Feature/first-rag-milestone`，使用英文提交及雙語 PR 草稿。初始里程碑完成時，使用者延後 GitHub 發布，因此當時沒有遠端 PR；後續已授權將版面與模型指南更新一起進行首次 GitHub 交付。後續 push／PR／checks／reviews／merge 請依 [AGENTS.md](../AGENTS.zh-TW.md)。

使用者隨後要求開源發布，已加入程式／文件的標準 MIT 授權；原創範例／產生程式維持 CC0。中英文 README 與貢獻說明均加入授權與 fork／PR 流程，GitHub 公開設定屬於本次明確授權的交付。

發布文件新增完整中英文使用／部署指南、十張已逐張檢查的實際介面圖，以及限定公開範例的圖片重現程式。`node scripts/capture_ui_docs.mjs` 完成真實英／中文問答，總耗時分別為 5,153.27 ms 與 885.26 ms。`systemd-analyze --user verify deploy/ragglass.service` 通過；保留既有 API，未啟用選用 user service、遠端 SSH 用戶端或完整備份／還原，也未將它們宣稱為已驗證。README 用途／功能／快速入口與 GitHub About／topics 便於理解及搜尋，不宣稱實際 Star 或曝光成果。

## 雙語曝光素材

**2026-10-03 UTC** 最後一次 `node scripts/capture_demo.mjs` 在 Chrome 新增兩題真實 `gemma4:e4b` 查詢，輸出英文／繁體中文字幕 H.264 影片（**54.791667 秒**、1440 × 1000、正常速度）、兩個十秒 GIF 與公開錄製來源紀錄。確認 30 MB 答案引用本次檢索到的第 2 頁、來源框線、解析表格、設定、無引用拒答與歷史重開。總查詢耗時為 **5,177.93 ms**、**898.10 ms**；第一題 Ollama 回報載入耗時 **4,626.75 ms**，不是單純已載入模型的推論測量。錄製重用範例已存在的索引，沒有獨立 GPU 使用測量。

`node scripts/render_social_preview.mjs` 以實際截圖產生中英 1280 × 640 封面，均低於 1 MB。`scripts/record_traffic.py` 實際唯讀取得 GitHub 基準，保存在已忽略的 `.data/traffic/`。新增雙語分享指南、發文草稿、表格來源案例、版本說明與 README 動畫，說明試用、重現、分享及成果觀察。準備 Social preview 圖檔不等於已設定 GitHub 圖片，官方網頁上傳仍為手動步驟。本次沒有發送社群貼文或建立定期排程。影片／字幕為 Release 附件，原始錄影保留本機。

## 限制與下一里程碑

目前只評估這份三頁原生文字範例與明確的契約輸入。尚未驗證或不在範圍內：真實 vLLM／OpenAI 服務、另一台電腦的 SSH 用戶端、掃描／純圖片 PDF、大規模 corpus、多使用者併發、對抗性語意支持檢查與正式部署強化。來源座標為 Docling 內容區塊範圍，不是精確句子邊界；引用存在不代表答案語意必然正確。沒有分散式工作佇列或解析續跑，中斷工作會標成可重試的失敗。

建議下個里程碑建立固定評測資料集與修改前後 run 比較，加入檢索 recall、回答正確性／faithfulness 指標，以及可替換的混合檢索與 reranker。OCR/VLM、診斷 Agent、embedding 微調保留為後續獨立 adapter。
