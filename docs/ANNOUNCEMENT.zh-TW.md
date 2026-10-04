# RAGGlass 發布文案草稿

[English](ANNOUNCEMENT.md) | **繁體中文**

草稿描述目前的原生文字 PDF 版本。發布前請加入自己真實的開發動機，確認能協助讀者試用。搭配[繁體中文字幕影片](https://github.com/KuoFengYuan/RAGGlass/releases/download/v0.1.0/ragglass-demo.zh-TW.mp4)或[分享封面](images/social-preview.zh-TW.png)。社群規則與第一週建議見[分享 RAGGlass](LAUNCH.zh-TW.md)。

## 短貼文

PDF RAG 的答案看起來不對時，你會怎麼確認原始來源？

我正在開發 RAGGlass：把原始 PDF、檢索證據與答案並排呈現的地端開源工作台。點引用即可回到來源頁面，也能查看保存的 prompt、設定與耗時。

試用公開範例：https://github.com/KuoFengYuan/RAGGlass

可選標籤：`#RAG #OpenSource #LocalAI`。依平台當時的字數限制調整，這份短稿不假設固定字數上限。

## 完整技術貼文

PDF RAG 能回傳看似合理的答案，卻常讓人難以確認模型看到了什麼：表格解析正確嗎？檢索找到正確那一列嗎？答案由哪一頁支持？

我正在開發 **RAGGlass — See inside your RAG.**，一個採 MIT 授權的地端工作台，用來檢視從文件到答案的完整路徑。

第一版可以：

- 上傳原生文字 PDF，查看 Docling 解析結果。
- 並排對照原始 PDF、檢索片段分數與真實模型回答。
- 點擊已驗證的來源 ID，跳回對應的原始頁面。
- 重新開啟歷史紀錄，查看 prompt、證據、設定、答案與各階段耗時。

影片詢問虛構試用方案的上傳限制，從 30 MB 答案回到第 2 頁表格，再問文件沒有記載的年度電費。模型推論是真實執行，錄製重用範例已存在的索引。

技術使用 Vue 3／PDF.js、FastAPI、Docling、Qdrant、SQLite、本機 E5 embedding，以及獨立 Ollama／相容 HTTP 模型服務，附完整英文與繁體中文操作／部署文件。

目前支援原生文字 PDF。向量／BM25／混合模式及小型固定條件中英文評測已實作，詳見[檢索指南](RETRIEVAL.zh-TW.md)。OCR、reranking、自動診斷與大規模正式評測仍待後續實作。來源 ID 驗證能檢查引用來自哪裡，無法直接證明每一句答案都有語意支持。

歡迎用公開範例試用，或回報去識別的解析／檢索重現問題：
https://github.com/KuoFengYuan/RAGGlass

如果對你的 RAG 工作有幫助，歡迎 Star，讓其他工程師找到它。

## Show HN 標題

正式投稿使用英文標題：
**Show HN: RAGGlass – Trace PDF RAG answers back to their source pages**

中文意思：RAGGlass，從 PDF RAG 答案追查到原始來源頁面。

投稿連結：https://github.com/KuoFengYuan/RAGGlass

## Show HN 首則留言草稿

RAGGlass 是給 PDF RAG 工程師的地端檢視工作台。原始 PDF 與檢索片段、答案並排，來源按鈕可回到原始頁面。SQLite／本機檔案保存實際 prompt、設定、證據、答案與耗時，向量保存在 Qdrant。

儲存庫包含三頁原創虛構 CC0 PDF、六個 smoke-test 問題、完整英文／繁體中文說明，以及錄製當下使用真實模型的操作影片。需要 Python 3.12、Node 20.19+、Docker Compose 及可連線的 Ollama／相容模型服務；首次下載依賴與模型需要網路。這是早期原生文字 PDF 版本，預設只綁 loopback。

實作將 parser、embedder、retriever 與回答模型 adapter 分開。引用必須屬於本次查詢檢索到的 ID，由後端映射到原始文件與頁碼，可避免不存在的來源連結；但語意是否支持答案仍需另外評測。

希望收到 PDF／表格證據檢視、安裝阻礙，以及哪些資訊能協助理解檢索失敗的回饋。歡迎用公開範例提供重現步驟。

發布前給作者的提醒：補上自己開發的具體原因，以及能親自討論的實作細節。實際 Show HN 投稿使用[英文對照](ANNOUNCEMENT.md)，依[Show HN 規則](https://news.ycombinator.com/showhn.html)發布；草稿邀請技術回饋，不要求投票。

## 後續案例貼文

要怎麼知道 PDF RAG 回答用了正確的表格列？

這份 RAGGlass 操作案例把真實本機模型答案，沿著檢索片段追查到原始頁面，再驗證文件無法回答的問題；附重現步驟，也說明引用驗證的能力與限制：

https://github.com/KuoFengYuan/RAGGlass/blob/main/docs/CASE_STUDY.zh-TW.md

這些都是已準備的草稿，出現在儲存庫不代表已發布或已帶來流量。
