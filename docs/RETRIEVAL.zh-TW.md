# 檢索模式與固定條件評測

[English](RETRIEVAL.md) | **繁體中文**

RAGGlass 可在不更換 PDF、parser、embedding 或回答模型的情況下，比較向量、關鍵字與混合檢索。開啟**檢索選項 → 檢索模式**即可切換。既有預設維持**向量**，舊 API 請求保持相容；已索引文件不必為關鍵字／混合模式另外遷移。

## 控制與分數

| 模式 | 檢索方式 | 證據分數 |
| --- | --- | --- |
| 向量（`dense`） | E5 問題向量 → Qdrant，在所選文件內搜尋 cosine 相似度。 | Cosine 相似度，不是答案正確機率。 |
| 關鍵字（`keyword`） | 對所選文件的 SQLite chunks 計算本機 BM25，略過問題向量化及向量查詢。 | 正值 BM25 相關性，不能直接與 cosine 比較。 |
| 混合（`hybrid`） | 各方法先找候選，依 chunk ID 去重，以等權重 RRF 合併排名。 | `sum(1 / (60 + 各路排名))`，不是機率。 |

**Top K** 是最終證據上限，預設 5、範圍 1–12。**最低分數**預設 0.70，只過濾 cosine 向量候選，混合模式亦然；不過濾 BM25 或 RRF，關鍵字模式會停用該欄位。**各方法候選片段數**僅在混合模式顯示，預設 20、最多 100，不能小於 Top K。候選未進入最終證據，或被 [context 預算](WORKFLOWS.zh-TW.md#context-與-token) 排除，就不能被模型引用。

證據卡會明確標示 cosine、BM25 或 RRF，並列出各路原始排名／分數。展開**檢索排名追蹤**可查看完整候選、來源頁碼、比對詞與哪些 ID 進入最終證據。缺少某一路排名表示不在該路保留的候選中，不代表相關性分數為零。途中停止的混合檢索會標示部分排名。歷史可恢復模式／候選數，JSON 與 Markdown 匯出保留診斷分數。歷史清單略去較大的候選 trace，詳情與匯出仍完整保存。

沒有候選時，會在推論前保存拒答。混合模式的向量服務失敗會明確失敗，不會悄悄換成其他方法。關鍵字模式仍要求文件已就緒且屬於目前 embedding 空間，以維持已索引文件的查詢條件。

## 實作與邊界

`keyword.py` 是可替換的獨立檢索器，與 Qdrant／模型 adapter 分離。查詢時讀取保存的 chunks，因此重新索引、刪除、重啟不必同步另一份文字索引。BM25 採 `k1=1.2`、`b=0.75`、去重的問題詞項，以及正值 IDF：`log(1 + (N - df + 0.5) / (df + 0.5))`。詞頻與長度統計只涵蓋所選文件；紀錄保存 corpus 片段數、問題詞項、分詞器／演算法版本與參數。

分詞使用 Unicode NFKC、大小寫正規化、拉丁／英數詞、保留標點分隔的完整型號及組成詞，以及漢字 unigram／bigram。`CEDAR-X17` 與 `CEDAR-X71` 保持不同，但共通組成詞仍可能找出其他型號。固定英文停用詞表隨實作版本保存。這不是中文語言學斷詞、詞幹還原、繁簡轉換或片語／完全匹配過濾；其他文字系統及 regex 範圍外的漢字擴充區仍待支援。

BM25 每次查詢都掃描／分詞所選片段，CPU 與記憶體成本隨文字量增加，適用本機工作台，不是大型 corpus 的倒排索引服務。既有 Qdrant dense collections、後端執行依賴與模型服務維持原設定。前端在開發與建置模式都提供本機 PDF.js CMap／標準字型資源，供中文 CID PDF 使用；由固定版本的依賴複製，保留資源授權，不透過 CDN。TypeScript 建置新增固定版本的 Node 型別依賴。Cosine 與 BM25 尺度不同，所以合併排名；RRF 並沒有學習相關性。同 RRF 分數先比較同一尺度內的 BM25 分數，再依向量排名與 chunk ID 排序。明確的同分規則能避免 BM25 同分時由無關 ID 決定語意偏好，但仍不保證相關性。候選深度、重複／重疊片段或無關關鍵字都可能讓結果變差。Reranker 留待後續 adapter；兩路都沒找出的來源，單靠 reranker 無法補回。仍要核對原文：引用 ID 合法不等於語意支持答案。

`dense_retrieval`、`keyword_retrieval`、`rank_fusion` 分別保存實際耗時，`retrieval` 是其合計，不能再把合計與子階段相加。問題 embedding 耗時另計，關鍵字模式沒有該階段。

## 一次比較一個條件

原 [12 題範例](../examples/evaluation-cases.json) 保留為 dense smoke baseline。新[八頁檢索實驗文件](../examples/ragglass-retrieval-lab.pdf)加入 [16 題中英文標註](../examples/retrieval-cases.json)，涵蓋型號／錯誤碼、數字／日期、相似紀錄、語意改寫及文件無答案情境。兩份文件與標註都是虛構 CC0 測試資料。上傳／索引實驗文件後，從文件詳情或 `/api/documents` 取得文件 ID。

固定問題、K／門檻／候選數及生成參數，只改檢索模式：

```bash
.venv/bin/python scripts/evaluate.py --document-id YOUR_LAB_ID --dataset examples/retrieval-cases.json --top-k 3 --retrieval-mode dense --output .data/dense.json
.venv/bin/python scripts/evaluate.py --document-id YOUR_LAB_ID --dataset examples/retrieval-cases.json --top-k 3 --retrieval-mode keyword --compare .data/dense.json --compare-axis retrieval --output .data/keyword.json
.venv/bin/python scripts/evaluate.py --document-id YOUR_LAB_ID --dataset examples/retrieval-cases.json --top-k 3 --retrieval-mode hybrid --compare .data/dense.json --compare-axis retrieval --output .data/hybrid.json
```

三次指令的候選數預設皆為 20、cosine 門檻皆為 0.70。必須明確指定 `--compare-axis retrieval`，才允許 mode／strategy 改變；生成／模型、資料集／文件／已保存片段 hash、parser／chunk／embedding／prompt、context／重試設定、候選數、K、門檻及關鍵字／融合演算法設定皆須相同。預設生成比較仍要求檢索設定完全一致。不符條件時回報 `comparable: false`，不把差值當成固定條件比較。

報告涵蓋來源頁 Recall@K、第一個正確來源頁的 reciprocal rank（MRR@K）、引用覆蓋、預期文字比對、可回答性／拒答、檢索與查詢耗時、已回報／未知 token、各題型分類及完整執行 trace。MRR 使用第一個包含任何標註頁的證據排名，屬頁面指標，不是 chunk／claim 相關性。無答案題沒有來源頁指標。找到正確頁仍可能被 context 預算排除，或不能支持生成答案。文字比對、小型虛構資料及單次循序執行都不能證明語意準確率、統計顯著性或普遍加速／品質提升。Temperature 0 不保證推論完全固定；模型權重與共用工作負載也有影響。

## 驗證與面試說明

```bash
bash scripts/check.sh
.venv/bin/python scripts/verify_retrieval.py
```

後者使用自己的暫存 loopback API／Qdrant 與儲存空間，重用已設定的模型服務。會執行原有真實流程檢查、先記錄 dense baseline、比較三種模式、檢查門檻／無證據、真正重啟自己的 API，並執行建置版 Chrome 流程。確認原有資料未改變後移除自己的服務。完整報告保存在忽略版控的 `.data/retrieval-verification.json` 與 `.data/retrieval-evaluation-{dense,keyword,hybrid}.json`；合成契約與真實證據分開，實測結果見[里程碑紀錄](MILESTONE.zh-TW.md)。

示範 `CEDAR-X17`／`CEDAR-X71` 或中文保存期限題，展開兩路候選、點最終引用，再比較評測報告。可口述：「向量檢索找相近語意，BM25 保留型號與關鍵詞。我用 RRF 合併排名，分開保存分數，評測時只改檢索模式。Trace 可以區分檢索遺漏、context 排除與生成錯誤；有退步的結果也如實報告。」[重新錄製的影片](DEMO.zh-TW.md#影片中的二十個步驟)展示中文 BM25、混合控制、兩路候選及來源查證；完整固定條件比較仍由獨立 CLI 執行。

演算法參考：[Introduction to Information Retrieval 的 BM25](https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html)、[RRF 原始論文](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)。上述正值 IDF 是此實作明確選擇的變體，不代表所有 BM25 套件產生相同分數。
