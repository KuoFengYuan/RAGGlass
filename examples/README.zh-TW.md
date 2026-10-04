# 原創 PDF 測試文件

[English](README.md) | **繁體中文**

`ragglass-field-guide.pdf` 是自行製作的三頁原生文字 PDF，含簡單設定表格，描述虛構的 Cedar 試用計畫。規格是虛構測試資料，並非實測效能。產生程式為 `scripts/make_sample.py`，使用 `.venv/bin/python scripts/make_sample.py` 重新產生。

範例 PDF 與產生程式以 [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) 釋出，可公開複製、修改及散布，未嵌入第三方內容。`questions.json` 提供六個問題與預期證據頁碼，包含無法由文件回答的問題。請先上傳 PDF；介面回答全部來自設定的真實模型，沒有預先計算的 demo 答案。

`evaluation-cases.json` 將標註擴充為十二題中英文案例，保存 PDF hash、正確來源頁、可回答與否及預期文字變體，標註同樣採 CC0。評測回報頁碼 recall 與文字比對，不冒充語意蘊含或正式環境準確率。見 [流程評測](../docs/WORKFLOWS.zh-TW.md)。

`scripts/verify_workflows.py` 在暫時儲存空間產生另一份六頁虛構原生文字客訴。Nora Lin、訂單 CL-204、金額與日期皆為虛構 CC0 測試資料；客訴文字與產生程式同樣採 CC0。產生的 PDF 與完整紀錄留在 Git 忽略的暫時空間，沒有使用私人上傳或提交文件。
