# RAGGlass v0.1.0 — 原生文字 PDF 預覽版

[English](RELEASE-v0.1.0.md) | **繁體中文**

**See inside your RAG.** 並排檢視原始 PDF、檢索證據與真實模型答案，再沿著引用回到來源頁面。首次公開預覽採 MIT 授權、地端執行，附完整英文／繁體中文指南。

## 試用此版本

從[README](../README.zh-TW.md)、[圖解操作](USAGE.zh-TW.md)與[部署指南](DEPLOYMENT.zh-TW.md)開始。需要 Linux、Python 3.12、Node 20.19+、Docker Compose，以及可連線的 Ollama／OpenAI 相容 HTTP 模型服務。預設 `gemma4:e4b` 已使用真實推論驗證，解析／embedding 使用 CPU，Qdrant 由明確版本的 Compose 啟動；首次下載依賴與模型需要網路。

[觀看繁體中文字幕影片](https://github.com/KuoFengYuan/RAGGlass/releases/download/v0.1.0/ragglass-demo.zh-TW.mp4) · [使用 CC0 PDF](../examples/ragglass-field-guide.pdf) · [六題範例問題](../examples/questions.json)

## 包含功能

- 以 Docling 上傳／索引原生文字 PDF，用 PDF.js 檢視原文。
- 以真實多語 E5 embedding／Qdrant 檢索，連接獨立 HTTP 模型服務生成答案。
- 只接受本次檢索內容的引用 ID，由後端對應原始文件／頁碼。
- 查看解析結果、可用的來源座標、分數、prompt、設定、模型 metadata 與實測階段耗時。
- 以 SQLite、本機檔案與 Qdrant 持久保存文件與歷史。
- 響應式文件工作台，預設繁體中文，持久保存英文切換選擇。
- 鎖定 uv／npm 依賴、預設 loopback，提供 SSH tunnel 預覽說明。
- 提供真實模型操作錄影、雙語封面、來源追查案例與技術發文草稿。

## 驗證

初始里程碑通過 **11 個契約／API 測試**、六題真實模型問答、開發／正式介面瀏覽器檢查、實際 API／Qdrant 重啟持久化，以及模型不可連線錯誤流程。[里程碑紀錄](MILESTONE.zh-TW.md)區分合成契約輸入與真實服務，並保存實測數字。

本次影片新增兩次真實查詢，檢查已知表格答案、本次檢索引用、PDF 第 2 頁／來源框線、解析表格、設定、無證據拒答、歷史重開與無瀏覽器錯誤。兩支影片共用英文介面的同次錄製，分別加上英文／繁體中文字幕；字幕在介面下方、維持正常速度，重用範例已存在的索引。[錄製來源紀錄](media/demo-recording.json)

素材檢查、完整 `bash scripts/check.sh` 與發布 PR 的 CI 結果記錄於 PR。原始錄影、依賴、快取、私人文件、金鑰及本機流量快照不進 Git；MP4 與字幕為 Release 附件。

## 範圍與下一步

本版是單人、loopback 預覽，沒有登入驗證，支援原生文字 PDF。尚未包含 OCR／VLM、混合檢索、reranking、自動診斷、正式品質評分與修改前後比較。引用屬於來源不等於語意支持答案，來源框線不代表精確詞句。其他推薦模型是候選，不是已測量的品質排名。真實 vLLM、遠端 SSH client、大型文件庫，以及選用 systemd／完整備份還原流程的未驗證範圍，詳見部署／里程碑文件。

下一個里程碑建議建立固定雙語評測集與可重現的修改前後比較，再加入可替換混合檢索與 reranker。

歡迎依[貢獻流程](../CONTRIBUTING.zh-TW.md)提交 issue／PR，使用公開或去識別文件重現問題。程式／文件採[MIT](../LICENSE)，原創範例／產生程式採 CC0；第三方依賴與模型維持各自授權。
