# RAGGlass

**See inside your RAG.**

[English](README.md) | **繁體中文**

可在地端部署的文件 RAG 診斷工作台，提供給開發文件 RAG 的工程師。從回答、檢索證據、解析內容追查回原始 PDF，檢視完整設定及各階段實測耗時；重啟服務後仍可開啟文件與執行紀錄。

第一里程碑以 Docling 處理原生文字 PDF、Qdrant 提供多語向量檢索，並透過獨立的模型 HTTP 服務生成有引用的回答。正式流程使用真實 embedding 與模型推論，沒有固定 demo 答案。[原創範例 PDF](examples/ragglass-field-guide.pdf) 描述虛構 Cedar 計畫，含簡單表格與[六個問題](examples/questions.json)，包含文件無法回答的問題。

![工作台並排顯示原始 PDF、答案與檢索證據](docs/images/workbench.png)

*英文介面的實際截圖，使用虛構 CC0 範例及即時 `gemma4:e4b` 回答；圖中耗時屬於該次執行。*

## 環境需求

- Linux/macOS、Python **3.12**、Node.js **20.19+**、npm 與 Docker Compose。實測主機為 Ubuntu 24.04、系統 Python 3.12.3、Node 20.20.2、Docker 29.3.0。
- 可連線的 Ollama 或 OpenAI 相容模型 API。本次重用既有本機 Ollama 及 `gemma4:e4b`；應用不會啟動、升級或管理該模型服務。
- 首次安裝依賴與下載 Docling／E5 模型需要網路。下載後解析與 embedding 在本機執行；模型 endpoint 指向本機服務即可本機推論。
- 預設 Docling 與 `intfloat/multilingual-e5-small` embedding 採 CPU、四個執行緒，GPU 由獨立模型服務使用。無須修改系統驅動。實測主機有兩張 NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition，詳細驗證、限制與耗時見[實測紀錄](docs/MILESTONE.zh-TW.md)。

## 本機設定

在專案根目錄執行：

```bash
# 使用既有具 pip 的 Python，將 uv 安裝在專案內。
python3 -m pip install --target .tools uv==0.8.22
export UV_CACHE_DIR="$PWD/.cache/uv"
.tools/bin/uv sync --frozen --python 3.12
npm --prefix frontend ci
cp .env.example .env
docker compose up -d qdrant
bash scripts/dev.sh
```

開啟 **http://127.0.0.1:5173**。API 位於 **http://127.0.0.1:8000**，API 文件在 `/docs`。Qdrant 使用 **127.0.0.1:6333** 與專用 `ragglass_qdrant_data` Docker volume。應用服務都只綁 loopback。Ctrl+C 停止開發服務，保留 Qdrant 與資料。也可分別在兩個 terminal 啟動：

```bash
.venv/bin/python -m uvicorn ragglass.main:app --app-dir backend --host 127.0.0.1 --port 8000
# 第二個 terminal：
npm --prefix frontend run dev
```

若缺少 Python 3.12，先執行 `UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" .tools/bin/uv python install 3.12`，讓 uv 將 Python 安裝在專案，再 sync。uv 不需要系統的 `python3.12-venv`／`ensurepip`。Python 依賴位於 `.venv`、Node 依賴位於 `frontend/node_modules`、模型快取位於 `.cache`。不可使用 `sudo pip` 或自行升級 GPU 驅動。

若要用單一伺服器提供正式建置的介面，先停止開發 API，再執行：

```bash
npm --prefix frontend run build
.venv/bin/python -m uvicorn ragglass.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

API 啟動時若有 `frontend/dist` 就會提供該介面，開啟 **http://127.0.0.1:8000**。沒有額外前端容器或雲端託管依賴。

## 模型設定

在啟動 API 前編輯 `.env`。預設重用既有服務：

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=gemma4:e4b
```

使用 `curl http://127.0.0.1:11434/api/tags` 確認實際模型，選擇已安裝且能遵循指令、輸出 JSON 的本機模型。地端／離線推論不要選 Ollama `:cloud` 模型。原生 Ollama adapter 要求符合 schema 的 JSON、預設關閉 thinking，並保存服務回報的模型／token／耗時資訊。首次模型載入可能較慢，預設逾時為 180 秒。

若使用既有 vLLM 或其他 OpenAI 相容服務：

```dotenv
LLM_PROVIDER=openai
LLM_BASE_URL=http://127.0.0.1:8001/v1
LLM_MODEL=your-served-model-name
LLM_API_KEY=
LLM_JSON_MODE=true
```

adapter 呼叫 `/chat/completions` 並要求 JSON；只有 API 拒絕此選項時才關閉 `LLM_JSON_MODE`。prompt 仍要求 JSON，引用驗證一樣必要。OpenAI 相容 adapter 有契約測試；本次既有 Ollama 足以完成地端推論，因此未實測新建 vLLM。專案容器映像都指定明確版本。

Embedding 使用 `.env.example` 的固定 E5 revision、正規化向量、`query: `／`passage: ` 前綴與模型 tokenizer。修改 embedding 設定後會使用不同 Qdrant collection，須重新索引既有文件才能查詢。Docling 自動下載 layout／table 模型；`DOCLING_CACHE_DIR` 是下載快取，選填的 `DOCLING_ARTIFACTS_PATH` 必須包含預先完整下載的模型。

### 建議的 Ollama 模型

於 **2026-10-03** 對照官方模型卡與 Ollama registry。以下是適合此工作台的候選方案，不宣稱某模型在所有情境都是最佳。通用程式／推理榜單無法證明文件回答品質、引用準確度或拒答可靠性。

| 回答模型 | 建議用途 | 本機驗證狀態 |
| --- | --- | --- |
| [`gemma4:e4b`](https://ollama.com/library/gemma4) | **預設與已驗證基準。** 適合先完成小型地端安裝及本 README 的範例流程。 | 已安裝，真實 PDF／模型／瀏覽器驗證通過；比較修改時保留此基準。 |
| [`qwen3.8:27b`](https://ollama.com/library/qwen3.8) | GPU 工作站的中英文文件問答**優先比較候選**。官方支援可設定的 thinking；先使用本應用關閉 thinking、要求 JSON 的設定。 | 本機確切名稱為 **`Qwen3.8:27b`**，正供其他工作使用；尚未量測它在 RAGGlass 的回答品質與延遲。 |
| [`gemma4:31b`](https://ollama.com/library/gemma4) | 記憶體與延遲預算允許時，作為 Gemma 家族較大型 dense 模型的比較對象。 | 已安裝，尚未在本應用評測。 |
| [`gemma4:12b`](https://ollama.com/library/gemma4:12b) | 27B／31B 不適用的機器可考慮此中型候選。 | 已查證官方 registry；本機未安裝、未測試，須確認 Ollama 版本相容性。 |

**實際建議：** 第一版保留 E4B 預設，下一步先比較 Qwen3.8-27B；若評測值得再比較 Gemma4-31B。實測主機有兩張各回報 97,887 MiB 的 GPU，但與其他工作共用。模型檔案大小不等於顯存需求；實際記憶體與延遲受量化、context、併發與推論引擎影響，不把未測候選的資源估計寫成實測值。

目前 `intfloat/multilingual-e5-small` 透過 Sentence Transformers 在本機 CPU 執行，Docling 的 layout／table 模型也採 CPU 且關閉 OCR；只有回答生成使用模型 HTTP API。以下 Ollama **embedding** 選項是後續 adapter 與評測的建議，不能用作回答模型：

| Embedding 模型 | 建議用途 | 整合狀態 |
| --- | --- | --- |
| [`qwen3-embedding:0.6b`](https://ollama.com/library/qwen3-embedding) | 優先評測的多語檢索候選，家族支援中英文與任務指令。 | 尚未整合或測試，須新增 Ollama `/api/embed` adapter。 |
| [`qwen3-embedding:4b`](https://ollama.com/library/qwen3-embedding) | 先測 0.6B，再評估較大型模型的召回提升是否值得資源成本。 | 尚未整合或測試。 |
| [`embeddinggemma:300m`](https://ollama.com/library/embeddinggemma) | 後續資源有限部署可評估的小型多語替代方案。 | 尚未整合或測試；registry 指定 Ollama 0.11.10 以上。 |

更換 embedding 必須處理模型專用指令／pooling、tokenizer、向量維度與正規化、新 collection、完整重新索引及檢索門檻校準。**不要把這些名稱填入 `LLM_MODEL`，也不能只換掉目前 E5 的環境設定。** 現有 adapter 使用 E5 專用前綴。Reranking 與多模態 PDF 檢索仍是未來功能；選擇支援視覺的回答模型不會啟用解析器的 OCR／VLM。

### 切換與驗證回答模型

```bash
# 先檢查既有服務，再決定是否需要下載。
curl -fsS http://127.0.0.1:11434/api/tags
# 只有選定模型尚未安裝時，下載一個候選：
ollama pull qwen3.8:27b
# 其他選擇：ollama pull gemma4:e4b / gemma4:31b / gemma4:12b
```

將**已安裝的確切名稱**填入 `.env`；此主機為 `Qwen3.8:27b`，新拉取官方模型通常為 `qwen3.8:27b`。已安裝不代表已通過應用相容性驗證。

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen3.8:27b
LLM_THINK=false
LLM_CONTEXT_TOKENS=8192
LLM_MAX_TOKENS=768
LLM_TIMEOUT_SECONDS=180
LLM_TEMPERATURE=0
```

**只重啟 RAGGlass API** 載入修改，以 `curl -fsS http://127.0.0.1:8000/api/config` 確認，再執行 `.venv/bin/python scripts/verify_e2e.py` 與下方瀏覽器檢查。更換回答模型不必重新索引文件。比較時固定 PDF、問題、prompt、檢索／切塊及生成選項，包含中英文表格題與無法回答的問題。檢查保存的答案及引用，不只看程式通過與否；六個範例問題屬於 smoke test，不是品質排名。

Ollama tag 可能在重新 pull 後改變。評測前使用 `curl -fsS http://127.0.0.1:11434/api/tags > .data/model-tags.json` 保存本機 metadata／digest；`.data` 不進 Git。每次查詢保存模型名稱／選項與回傳指標，但不封存權重，重現時須保留已測權重。第一版 E4B digest 及實測耗時見[里程碑紀錄](docs/MILESTONE.zh-TW.md)。本次更新建議未下載模型、替換預設模型或重啟共用 Ollama。

## 完整操作流程

1. 從文件工具列下載範例，或選擇 `examples/ragglass-field-guide.pdf` 上傳。狀態依序顯示等待、解析、切塊、向量化、索引、完成。首次處理含模型下載時間，處理中也能查看原始 PDF。
2. 詢問 **What is the maximum upload size for the Cedar pilot?**，預期事實為 **30 MB**，來自**第 2 頁**表格。答案由模型即時產生。
3. 點擊回答下的引用按鈕，PDF.js 會跳到對應頁面並標示可用來源內容區塊座標。點選檢索片段可展開全文、完整 chunk ID、cosine 分數、頁碼與座標可用性；也可直接點選頁碼列瀏覽原始頁面。
4. 開啟**解析內容**查看 chunks，或下載原始 Markdown／Docling JSON。文件詳情包含 SHA-256、解析／切塊／embedding 設定與處理耗時。
5. 查看執行耗時、展開設定與 prompt，或下載 run JSON。每次保存確切證據、prompt、模型 endpoint／名稱／選項、tokenizer revision、切塊與檢索設定，不保存 API key。
6. 詢問 **What is the pilot's annual electricity cost in dollars?**，應明確表示無法從文件確認，且不顯示引用。
7. 不刪除儲存資料的情況下重啟 API 與 Qdrant，既有文件與紀錄仍存在。在頂部導覽開啟**執行紀錄**，點選保存的查詢即可恢復答案、證據與當時設定。

工作台左側為原始 PDF，右側為問題／答案／證據檢視面板，底部顯示實測執行耗時。頂部導覽的**文件庫**與**執行紀錄**開啟清單對話框，也可透過文件選單切換目前文件；窄螢幕將 PDF 與檢視面板改為垂直排列。

介面預設繁體中文，可在右上角切換英文，偏好在重新整理後保留。目前後端的可處理錯誤訊息使用繁體中文。

## 透過 SSH 遠端預覽

當應用運行於遠端主機時，在自己的電腦執行：

```bash
ssh -N -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 user@your-host
```

在本機開啟 `http://127.0.0.1:5173`，或正式建置介面的 port 8000。瀏覽器以相對 `/api` 路徑經 Vite proxy 呼叫後端，無須公網綁定、reverse proxy 或雲端部署。已提供 tunnel 操作方法；實際遠端用戶端連線須在自己的網路驗證。

## 驗證

```bash
bash scripts/check.sh
# API、Qdrant 與真實模型服務運行時：
.venv/bin/python scripts/verify_e2e.py
npm --prefix frontend run test:e2e
# 驗證 FastAPI 直接提供的正式建置介面：
RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e
```

契約測試包含有效／無效引用、錯誤模型格式、實際 TCP 拒絕連線、SQLite 持久化、中斷作業復原及敏感資訊排除。這些採小型、明確標示的合成輸入，不冒充真實推論。

`verify_e2e.py` 上傳範例、檢查 Docling 頁碼與座標、確認已知證據，並向真實模型詢問全部六題，實測紀錄寫入 Git 忽略的 `.data/verification.json`。瀏覽器測試涵蓋上傳、即時問答、來源跳頁、重新整理後紀錄、語言切換、文件／頁碼導覽、鍵盤關閉對話框、檢索輸入驗證及 390 像素手機版面。預設使用本機 Google Chrome；也可用 `PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/playwright" frontend/node_modules/.bin/playwright install chromium` 安裝，再以 `RAGGLASS_BROWSER=chromium` 執行測試。沒有 NVIDIA GPU 的電腦仍可使用 CPU 啟動 API；量測程式會標示 GPU 遙測不可用，不虛構數據。

## 資料與架構

```text
Vue + PDF.js → FastAPI → Docling → 逐頁 token 切塊 → 本機 E5 → Qdrant
                   └─ 查詢 → E5 → 檢索證據 → 模型 HTTP API
                                         → 引用驗證 → 保存執行紀錄
SQLite：文件 metadata、chunks、runs     本機檔案：PDF、Markdown、Docling JSON
```

Adapter 分別是 `parser.py`、`embedding.py`、`retrieval.py`、`llm.py`，由 `pipeline.py` 協調。背景文件處理依序執行，控制 CPU 記憶體使用；查詢工作與 UI 請求迴圈分開。SQLite 為 metadata 的主要來源，可透過重新索引文件重建 Qdrant。每個 chunk 保存全部來源頁碼，包含跨頁內容。座標源自 Docling 原始內容區塊，可能大於個別 token 視窗，並非虛構的精確句子邊界；缺失座標則明確標示。

`.data/documents/<document-id>/` 保存 `original.pdf`、`parsed.md`、`docling.json`；`.data/ragglass.sqlite3` 保存 metadata／chunks／runs。請一起備份 `.data` 及 Qdrant volume。`docker compose down` 保留 volume，**`docker compose down -v` 會刪除向量儲存**。Git 忽略 `.env`、資料、快取、依賴、建置產物及本機報告；只有範例 PDF 預期公開。

## 限制與下一里程碑

目前只支援原生文字 PDF，尚未加入 OCR/VLM、混合檢索、reranker、正式品質指標、診斷 Agent 或 embedding 微調。引用驗證保證來源屬於本次檢索、且映射到文件／頁碼，不保證每句答案都受到語意支持。拒答依賴 prompt，廣泛對抗可靠性仍須評測。這是單人、loopback 工作台，沒有登入、分散式工作佇列、多租戶隔離或正式部署強化。重啟時進行中的作業標為失敗，供重試，不會悄悄續跑。本次未驗證遠端 vLLM、SSH 用戶端網路、掃描文件與大規模 corpus。

建議下一里程碑建立可重現的修改前後評測：固定問題集、檢索／回答指標、run 比較，以及可替換的混合檢索與 reranker。詳見[里程碑紀錄](docs/MILESTONE.zh-TW.md)、[貢獻流程](CONTRIBUTING.zh-TW.md)與 [Agent 規則](AGENTS.zh-TW.md)。PR 以英文優先並附繁體中文摘要，不可提交私人文件或憑證。
