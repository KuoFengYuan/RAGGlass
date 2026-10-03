# RAGGlass 安裝與部署

[English](DEPLOYMENT.md) | **繁體中文**

本指南在單一 Linux 主機執行 RAGGlass：CPU 解析／embedding、Docker Qdrant 持久化，以及獨立模型 HTTP 服務。開發時使用 Vite，日常使用可由 FastAPI 提供正式建置的前端；兩者預設綁 loopback，遠端透過 SSH 存取。此版本是沒有登入機制的單人工作台，支援的預覽方式會將服務連接埠保持在本機。

圖解流程請看[使用指南](USAGE.zh-TW.md)，模型用途及驗證狀態請看 [README](../README.zh-TW.md#建議的-ollama-模型)。

## 服務與需求

| 元件 | 用途 | 預設地址／儲存 |
| --- | --- | --- |
| FastAPI | 上傳、文件處理、查詢、歷史；提供正式介面 | `127.0.0.1:8000`；`.data` |
| Vite | 開發前端與 `/api` proxy | `127.0.0.1:5173`；只需開發時啟動 |
| Qdrant v1.15.5 | 向量索引 | `127.0.0.1:6333`；`ragglass_qdrant_data` volume |
| Ollama／相容 API | 回答生成，獨立管理 | Ollama 預設 `127.0.0.1:11434` |
| Docling／E5 | 原生文字解析與 embedding | CPU、專案 `.cache` |

已驗證主機為 **Ubuntu 24.04 x86_64、Python 3.12.3、Node 20.20.2、npm 10.8.2、Docker 29.3.0／Compose v5.1.0**。使用 Python **3.12** 與 Node **20.19+**。未驗證 macOS／Windows 原生安裝，包含固定 `torch==2.8.0+cpu` wheel 的相容性；這兩種平台可作為 Linux 主機的瀏覽器／SSH 用戶端。

FastAPI／Docling／E5 不要求 GPU。模型服務須具備所選模型需要的 CPU／GPU 資源，優先重用既有服務並保留其他 GPU 工作。首次下載依賴／模型需要網路；完成後若 LLM endpoint 指向本機，預設流程留在地端。

啟動前檢查：

```bash
python3 --version
node --version
npm --version
docker --version
docker compose version
docker ps
ss -ltnp
free -h
df -h .
# 有 NVIDIA 環境時，檢查完整型號、顯存與既有工作：
nvidia-smi
```

不要為本應用升級 GPU 驅動。缺少 Docker 權限或必要 interpreter／runtime 時，請主機管理者處理具體缺項。[Docker Compose 官方安裝](https://docs.docker.com/compose/install/)及 [Ollama Linux 官方安裝](https://docs.ollama.com/linux)與本 repository 的應用設定分開。

## 1. 建立專案內環境

全新 checkout：

```bash
git clone https://github.com/KuoFengYuan/RAGGlass.git
cd RAGGlass
python3 -m pip install --target .tools uv==0.8.22
export UV_CACHE_DIR="$PWD/.cache/uv"
.tools/bin/uv sync --frozen --python 3.12
npm --prefix frontend ci
if [ ! -f .env ]; then cp .env.example .env; fi
```

Python 依賴在 `.venv`、Node 依賴在 `frontend/node_modules`、下載快取在專案內。重現時保留 `uv.lock` 與 `frontend/package-lock.json`。Bootstrap Python 需具備 pip；即使系統 Python 缺少 `ensurepip`，uv 仍可建立虛擬環境。

若無 Python 3.12，但 bootstrap Python 可用：

```bash
UV_PYTHON_INSTALL_DIR="$PWD/.tools/python" .tools/bin/uv python install 3.12
.tools/bin/uv sync --frozen --python 3.12
```

依實際模型編輯 `.env`。Git 忽略 `.env` 與執行資料，更新時不要覆蓋既有 `.env`。程序提供的環境變數優先於檔案。

## 2. 連接獨立模型服務

先檢查既有 Ollama：

```bash
curl -fsS http://127.0.0.1:11434/api/tags
```

使用已安裝的確切名稱，例如此主機的候選別名 `Qwen3.8:27b`。已量測預設為：

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=gemma4:e4b
LLM_API_KEY=
LLM_THINK=false
LLM_CONTEXT_TOKENS=8192
LLM_MAX_TOKENS=768
LLM_TIMEOUT_SECONDS=180
```

只有沒有既有服務，且已安裝 Ollama binary 時，才可選擇另一個 terminal 執行：

```bash
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/.cache/ollama" ollama serve
# 另一個 terminal，僅在所選模型未安裝時：
ollama pull gemma4:e4b
```

這是選用的新服務操作指引，不代表本次實測另啟服務。既有 Ollama 部署保留原模型路徑。修改 RAGGlass 設定只重啟 API，不重啟共用模型服務；離線用途選本機模型，`:cloud` 會呼叫遠端。

既有 vLLM 或其他相容服務可設定：

```dotenv
LLM_PROVIDER=openai
LLM_BASE_URL=http://127.0.0.1:8001/v1
LLM_MODEL=your-served-model-name
LLM_API_KEY=
LLM_JSON_MODE=true
```

服務要求時才填 API key，存於 `.env`，不要放在 URL 或提交。原生 Ollama 有真實驗證，相容 adapter 有合成契約測試，新建 vLLM 尚未實測。不要將 embedding 名稱填為 `LLM_MODEL`。

## 3. 啟動持久化 Qdrant

```bash
docker compose up -d qdrant
docker compose ps
curl -fsS http://127.0.0.1:6333/healthz
```

[compose.yaml](../compose.yaml) 固定 `qdrant/qdrant:v1.15.5`，只公開本機 6333。Compose 預設專案名稱 `ragglass`，Docker 建立並重用 `ragglass_qdrant_data`；自行更改專案名稱時，備份／還原前先查實際 volume 名稱。`restart: unless-stopped` 只適用於 Qdrant，不會自動管理手動啟動的 API／模型服務。

## 4A. 開發模式

```bash
bash scripts/dev.sh
```

開啟 **http://127.0.0.1:5173**。程式啟動 FastAPI／Vite，Ctrl+C 停止本專案程序並保留 Qdrant／資料；須先完成第一步的 `.venv` 與前端依賴。

也可使用兩個 terminal：

```bash
# Terminal 1，專案根目錄：
.venv/bin/python -m uvicorn ragglass.main:app --app-dir backend --host 127.0.0.1 --port 8000
# Terminal 2，專案根目錄：
npm --prefix frontend run dev
```

一次使用一種啟動方法，8000 的 API 或 5173 的 Vite 已運行時不要重複啟動。

## 4B. FastAPI 提供正式建置介面

先停止本專案的開發 API，再從根目錄執行：

```bash
npm --prefix frontend run build
.venv/bin/python -m uvicorn ragglass.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

開啟 **http://127.0.0.1:8000**。API 啟動前須已有 `frontend/dist`，此模式不需 Vite；同一伺服器提供 `/api` 與 `/docs`。請從專案根目錄啟動，使相對快取路徑一致。這是已驗證部署方式；目前 Compose 只執行 Qdrant，不包含完整應用。

### 選用 Linux 使用者服務

[deploy/ragglass.service](../deploy/ragglass.service) 提供不需 root 的正式 API 服務，假設 checkout 位於 `~/repo/RAGGlass`。路徑不同時，須同時修改 **WorkingDirectory** 與 **ExecStart**。先建置／設定應用，確認 Qdrant／模型可用，並停止手動運行的 API 再啟用。

```bash
mkdir -p "$HOME/.config/systemd/user"
cp deploy/ragglass.service "$HOME/.config/systemd/user/ragglass.service"
# checkout 在其他位置時，先編輯已安裝的 unit。
systemd-analyze --user verify "$HOME/.config/systemd/user/ragglass.service"
systemctl --user daemon-reload
systemctl --user enable --now ragglass.service
systemctl --user status ragglass.service
journalctl --user -u ragglass.service -f
```

程式／設定更新後使用 `systemctl --user restart ragglass.service`，停止則使用 `systemctl --user stop ragglass.service`。Unit 可重啟失敗的 API，不負責管理 Docker／Ollama；登入工作階段外的啟動取決於主機 systemd user-session 設定。本次已實測語法檢查，未在該主機啟用服務，也未驗證登出／開機自動啟動。

## 5. 驗證就緒與完整流程

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/config
bash scripts/check.sh
.venv/bin/python scripts/verify_e2e.py
```

Health 應回報 `qdrant: ready`／`llm: ready`，`/api/config` 顯示實際載入設定且排除 API key；這不代表 GPU／品質 benchmark。開啟介面、上傳範例、等已索引、詢問上傳容量、點第 2 頁引用，再從執行紀錄重開，詳見[圖解操作指南](USAGE.zh-TW.md)。

瀏覽器檢查：

```bash
npm --prefix frontend run test:e2e
RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e
```

第一個對開發 5173，第二個對正式 8000，預設使用 Chrome。缺少時可安裝專案內 Chromium：

```bash
PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/playwright" frontend/node_modules/.bin/playwright install chromium
RAGGLASS_BROWSER=chromium RAGGLASS_BASE_URL=http://127.0.0.1:8000 npm --prefix frontend run test:e2e
```

Linux 瀏覽器 OS library 可能需要管理者安裝，這影響瀏覽器測試而非 API。圖片擷取程式使用同一瀏覽器選擇方式。

## 6. SSH 遠端預覽

在**自己的電腦**執行，遠端應用仍綁 loopback：

```bash
# 正式介面：
ssh -N -L 8000:127.0.0.1:8000 user@your-host
# 開發介面，另一種選擇：
ssh -N -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 user@your-host
```

瀏覽器開對應本機 port。本機 8000 被占用時可改用 `-L 18000:127.0.0.1:8000`，開啟 `http://127.0.0.1:18000`；正式介面使用相對 `/api`，無須修改前端。Qdrant／Ollama 不需向瀏覽器轉發。

本里程碑未從其他電腦實測 SSH 用戶端網路。GitHub 專案公開不會讓執行中的應用／上傳 PDF 自動公開；公網／多使用者託管需要另加登入、權限隔離及部署設計，不在此版本範圍。

## 7. 保存、備份與更新資料

| 路徑／volume | 內容 | 保存方式 |
| --- | --- | --- |
| `.data/ragglass.sqlite3` | 文件、chunks、runs、prompt／設定、證據、錯誤、耗時 | 與文件檔案一起備份。 |
| `.data/documents/` | 原始 PDF、解析 Markdown、Docling JSON | 與 SQLite 一起備份。 |
| `ragglass_qdrant_data` | 向量 collections | 保留 volume，或重新索引重建。 |
| `.cache/` | 已下載 parser／embedding 產物 | 離線使用須保留，可重新下載。 |
| `.env` | Endpoint／選項與選填憑證 | 個別私下保存。 |

`docker compose stop qdrant`／`docker compose down` 會保留 volume，**`docker compose down -v` 會刪除它**。需要保留文件／歷史時不要刪 `.data`。

一致備份先只停止 RAGGlass API，再停止本專案 Qdrant。以下以已固定版本的 Qdrant image 作為 tar 工具：

```bash
docker compose stop qdrant
ragglass_backup_dir="$PWD/.data/backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$ragglass_backup_dir"
tar --exclude=.data/backups -czf "$ragglass_backup_dir/data.tgz" .data
docker run --rm --entrypoint tar \
  --mount type=volume,src=ragglass_qdrant_data,dst=/storage,readonly \
  qdrant/qdrant:v1.15.5 -czf - -C /storage . > "$ragglass_backup_dir/qdrant.tgz"
docker compose up -d qdrant
# 依自己的啟動方式重啟 API。
```

在主機外保留另一份備份。還原使用全新 checkout 與空的目標 volume，API／Qdrant 保持停止；將 `ragglass_backup_dir` 設為實際封存資料夾：

```bash
tar -xzf "$ragglass_backup_dir/data.tgz" -C .
docker volume create ragglass_qdrant_data
docker run --rm -i --entrypoint tar \
  --mount type=volume,src=ragglass_qdrant_data,dst=/storage \
  qdrant/qdrant:v1.15.5 -xzf - -C /storage . < "$ragglass_backup_dir/qdrant.tgz"
```

恢復私下保存的 `.env`，使用相同 embedding 設定後啟動服務。這是復原指引，本次未執行完整封存／還原；已確認 Qdrant image 有 tar，也已實測 API／Qdrant 重啟持久化。Docker 官方說明見 [volume 生命週期與備份方式](https://docs.docker.com/engine/storage/volumes/)。

更新原始碼時，保留本機工作並在停止 API 前完成備份：

```bash
git pull --ff-only
export UV_CACHE_DIR="$PWD/.cache/uv"
.tools/bin/uv sync --frozen --python 3.12
npm --prefix frontend ci
bash scripts/check.sh
# 正式模式：check.sh 建置 frontend/dist 後，再重啟 API。
```

不要重複複製 `.env` 覆蓋設定。回答模型改變須重啟 API；embedding／切塊改變須重新索引，舊查詢快照仍可查看。

## 故障排查

| 狀況 | 檢查／處理 |
| --- | --- |
| 瀏覽器無法連後端 | 確認 API 在 8000，開發時 Vite 在 5173；遠端查 SSH mapping。 |
| Port 已被使用 | 用 `ss -ltnp` 查服務；重用既有專案實例或只停止屬於自己的程序，保留其他服務。 |
| 模型未提供 | 查 `/api/tags`，將確切名稱填入 `.env`，重啟 API；cloud／embedding 用途不同。 |
| `llm_unavailable`／逾時 | 查 endpoint、模型日誌、資源與 `LLM_TIMEOUT_SECONDS`；證據及失敗紀錄已保存。 |
| `invalid_model_response`／`invalid_citation` | 查保存的 raw response／prompt，重試或改用支援 JSON 的相容模型；未知引用會拒絕。 |
| Qdrant 不可用 | 查 `docker compose ps`、`docker compose logs qdrant`、6333／`QDRANT_URL`，啟動本專案容器。 |
| 解析失敗 | 使用符合限制、未加密的原生文字 PDF，依文件錯誤修正後重新索引；OCR 已關閉。 |
| 首次處理較慢 | 查下載連線、磁碟與專案快取；後續可重用產物。 |
| PDF 未顯示 | 開原始 PDF 連結，查瀏覽器 console／network 與保存文件是否可用。 |
| 無證據／答案不足 | 查解析片段、問題措辭、Top K／最低分數；文件缺少事實時拒答是正確行為。 |
| Embedding 設定改變 | 重新索引新向量空間，不混用不同空間或套用不相容的 E5 前綴。 |
| 重啟中斷索引 | 中斷工作標為失敗，可重新索引；已完成文件／歷史仍保存。 |

實測項目與限制見[里程碑紀錄](MILESTONE.zh-TW.md)。回到 [README](../README.zh-TW.md)。
