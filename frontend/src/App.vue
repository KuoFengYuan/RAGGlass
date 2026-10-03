<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from './api'
import PdfViewer from './PdfViewer.vue'
import type { Citation, Config, Document, Evidence, Run } from './types'

const locale = ref(localStorage.getItem('ragglass-language') || 'zh-TW')
const labels = {
  en: {
    workspace: 'Document workbench',
    local: 'Local workspace',
    docs: 'Documents',
    upload: 'Upload PDF',
    uploadHint: 'Native-text PDF · up to',
    sample: 'Download sample PDF',
    noDocs: 'Start with a document',
    noDocsHint:
      'Upload your PDF or download the field guide to trace a real answer back to its source.',
    original: 'Original PDF',
    parsed: 'Parsed content',
    question: 'Ask the document',
    placeholder: 'What is the maximum upload size for the Cedar trial?',
    ask: 'Retrieve & answer',
    asking: 'Retrieving & generating…',
    evidence: 'Retrieved evidence',
    answer: 'Grounded answer',
    noRun: 'Every answer starts with evidence.',
    noRunHint: 'Ask a question to inspect retrieved chunks, citations, and timing side by side.',
    verified: 'Citations validated',
    insufficient: 'Insufficient evidence',
    chunks: 'chunks',
    pages: 'pages',
    model: 'Model',
    topk: 'Top K',
    threshold: 'Minimum score',
    settings: 'Run settings & prompt',
    history: 'Run history',
    noHistory: 'Your queries and settings will appear here.',
    retry: 'Reindex',
    source: 'Source',
    noCoords: 'Coordinates unavailable',
    coords: 'Source item coordinates',
    score: 'Cosine score',
    trace: 'Execution trace',
    selected: 'Active document',
    pdfHint: 'Select an evidence card or citation to navigate to the source page.',
    download: 'Download run JSON',
    saved: 'Saved locally',
    failed: 'Failed',
    ready: 'Indexed',
    queued: 'Queued',
    parsing: 'Parsing',
    chunking: 'Chunking',
    embedding: 'Embedding',
    indexing: 'Indexing',
    demoQuestion: 'Example question',
    allChunks: 'Parsed chunks',
    close: 'Close',
    noEvidence: 'No evidence passed the score threshold. Try rephrasing or lowering the threshold.',
    documentDetails: 'Document settings & timings',
    apiError: 'Cannot reach the backend. Start the API on port 8000 and try again.',
    modelMissing: 'Model not available. Check LLM_MODEL and your model service.',
    depends: 'Service status',
    reset: 'Refresh',
    sampleLabel: 'Sample PDF',
  },
  'zh-TW': {
    workspace: '文件診斷工作台',
    local: '本機工作空間',
    docs: '文件',
    upload: '上傳 PDF',
    uploadHint: '原生文字 PDF · 上限',
    sample: '下載範例 PDF',
    noDocs: '從一份文件開始',
    noDocsHint: '上傳 PDF，或下載範例文件，將真實模型回答追查回原始證據。',
    original: '原始 PDF',
    parsed: '解析內容',
    question: '向文件提問',
    placeholder: 'Cedar 試用方案的上傳容量上限是多少？',
    ask: '檢索並回答',
    asking: '正在檢索與生成…',
    evidence: '檢索證據',
    answer: '模型回答',
    noRun: '每個回答，從證據開始。',
    noRunHint: '輸入問題，並排查看檢索片段、引用來源與執行耗時。',
    verified: '引用已驗證',
    insufficient: '證據不足',
    chunks: '片段',
    pages: '頁',
    model: '模型',
    topk: 'Top K',
    threshold: '最低分數',
    settings: '執行設定與 Prompt',
    history: '執行紀錄',
    noHistory: '查詢與設定將保存於此。',
    retry: '重新索引',
    source: '來源',
    noCoords: '無原始座標',
    coords: '原始內容區塊座標',
    score: 'Cosine 分數',
    trace: '執行耗時',
    selected: '目前文件',
    pdfHint: '點擊證據或引用，即可跳到原始頁面；框線標示內容區塊。',
    download: '下載執行 JSON',
    saved: '已保存於本機',
    failed: '失敗',
    ready: '已索引',
    queued: '等待處理',
    parsing: '解析中',
    chunking: '切塊中',
    embedding: '向量化中',
    indexing: '索引中',
    demoQuestion: '範例問題',
    allChunks: '解析片段',
    close: '關閉',
    noEvidence: '沒有片段通過分數門檻。請改寫問題或調低最低分數。',
    documentDetails: '文件設定與耗時',
    apiError: '無法連線後端。請啟動 port 8000 的 API 後重試。',
    modelMissing: '模型尚未提供。請檢查 LLM_MODEL 與模型服務。',
    depends: '服務狀態',
    reset: '重新整理',
    sampleLabel: '範例 PDF',
  },
}
type LabelKey = keyof typeof labels.en
const t = (key: LabelKey) => labels[locale.value === 'en' ? 'en' : 'zh-TW'][key]
const docs = ref<Document[]>([])
const runs = ref<Run[]>([])
const selectedId = ref('')
const document = computed(() => docs.value.find((d) => d.id === selectedId.value))
const run = ref<Run | null>(null)
const selectedEvidence = ref<Evidence | Citation | null>(null)
const page = ref(1)
const question = ref('')
const topK = ref(5)
const threshold = ref(0.7)
const config = ref<Config | null>(null)
const health = ref<Record<string, string>>({})
const error = ref('')
const uploading = ref(false)
const querying = ref(false)
const view = ref('pdf')
const parsedChunks = ref<Evidence[]>([])
const fileInput = ref<HTMLInputElement>()
let refreshTimer: ReturnType<typeof setInterval>
const provenance = computed(() =>
  selectedEvidence.value?.document_id === selectedId.value ? selectedEvidence.value.provenance : [],
)
const ms = (value: number) =>
  value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value.toFixed(0)} ms`
const date = (value: string) =>
  new Date(value).toLocaleString(locale.value === 'en' ? 'en-US' : 'zh-TW', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
const status = (value: string) => (value in labels.en ? t(value as LabelKey) : value)

function setLocale() {
  localStorage.setItem('ragglass-language', locale.value)
  window.document.documentElement.lang = locale.value === 'en' ? 'en' : 'zh-Hant'
}

async function refresh() {
  try {
    const [documents, history, dependency] = await Promise.all([
      api<Document[]>('/documents'),
      api<Run[]>('/runs'),
      api<{ dependencies: Record<string, string> }>('/health'),
    ])
    docs.value = documents
    runs.value = history
    health.value = dependency.dependencies
    if (!selectedId.value && documents.length) selectedId.value = documents[0].id
  } catch (e) {
    error.value = `${t('apiError')} ${(e as Error).message}`
  }
}

async function selectDocument(id: string) {
  selectedId.value = id
  page.value = 1
  selectedEvidence.value = null
  parsedChunks.value = []
  if (view.value === 'parsed') await loadChunks()
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    const data = new FormData()
    data.append('file', file)
    const doc = await api<Document>('/documents', { method: 'POST', body: data })
    await refresh()
    await selectDocument(doc.id)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    uploading.value = false
    input.value = ''
  }
}

async function reindex() {
  if (!document.value) return
  try {
    await api(`/documents/${selectedId.value}/reindex`, { method: 'POST' })
    await refresh()
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function ask() {
  if (!question.value.trim() || !document.value || querying.value) return
  querying.value = true
  error.value = ''
  selectedEvidence.value = null
  try {
    run.value = await api<Run>('/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: question.value,
        document_ids: [selectedId.value],
        top_k: topK.value,
        score_threshold: threshold.value,
      }),
    })
    await refresh()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    querying.value = false
  }
}

async function openRun(id: string) {
  try {
    run.value = await api<Run>(`/runs/${id}`)
    question.value = run.value.question
    const retrieval = run.value.settings.retrieval as { top_k: number; score_threshold: number }
    topK.value = retrieval.top_k
    threshold.value = retrieval.score_threshold
    if (run.value.document_ids[0]) await selectDocument(run.value.document_ids[0])
  } catch (e) {
    error.value = (e as Error).message
  }
}

function navigate(source: Evidence | Citation, targetPage = source.page) {
  selectedId.value = source.document_id
  page.value = targetPage
  selectedEvidence.value = source
  view.value = 'pdf'
}

async function loadChunks() {
  view.value = 'parsed'
  if (selectedId.value) {
    try {
      parsedChunks.value = await api<Evidence[]>(`/documents/${selectedId.value}/chunks`)
    } catch (e) {
      error.value = (e as Error).message
    }
  }
}

function downloadRun() {
  if (!run.value) return
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(run.value, null, 2)], { type: 'application/json' }),
  )
  const link = window.document.createElement('a')
  link.href = url
  link.download = `ragglass-run-${run.value.id}.json`
  link.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  setLocale()
  try {
    config.value = await api<Config>('/config')
    topK.value = config.value.retrieval.top_k
    threshold.value = config.value.retrieval.score_threshold
  } catch (e) {
    error.value = (e as Error).message
  }
  await refresh()
  refreshTimer = setInterval(refresh, 4000)
})
onBeforeUnmount(() => clearInterval(refreshTimer))
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="/" aria-label="RAGGlass home">
        <svg class="brand-mark" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="11" fill="#183b31" />
          <path d="M10 11h16v5H15v13h-5V11Z" fill="#a9edc9" />
          <path d="M20 21h10v10H20V21Z" stroke="#a9edc9" stroke-width="3" />
        </svg>
        <span>RAG<span class="brand-light">Glass</span><small>See inside your RAG.</small></span>
      </a>
      <div class="workspace-label">
        <span class="status-dot" />{{ t('local') }}<span class="mono">M1</span>
      </div>
      <div class="sidebar-heading">
        {{ t('docs') }} <span>{{ docs.length }}</span>
      </div>
      <input ref="fileInput" type="file" accept="application/pdf,.pdf" hidden @change="upload" />
      <button class="upload-button" :disabled="uploading" @click="fileInput?.click()">
        <span>＋</span>{{ uploading ? '…' : t('upload') }}
      </button>
      <p class="upload-hint">{{ t('uploadHint') }} {{ config?.max_upload_mb || 30 }} MB</p>
      <nav class="document-list" aria-label="Documents">
        <button
          v-for="doc in docs"
          :key="doc.id"
          class="document-item"
          :class="{ active: selectedId === doc.id }"
          @click="selectDocument(doc.id)"
        >
          <span class="file-icon">PDF</span
          ><span class="document-text"
            ><strong>{{ doc.filename }}</strong
            ><small
              ><i class="status-dot" :class="doc.status" />{{ status(doc.status) }} ·
              {{ doc.page_count }} {{ t('pages') }}</small
            ></span
          >
        </button>
      </nav>
      <a class="sample-link" href="/api/sample.pdf" download="ragglass-field-guide.pdf"
        >↓ {{ t('sample') }}</a
      >
      <div class="sidebar-heading history-heading">
        {{ t('history') }} <span>{{ runs.length }}</span>
      </div>
      <div class="history-list">
        <p v-if="!runs.length" class="muted tiny">{{ t('noHistory') }}</p>
        <button
          v-for="item in runs"
          :key="item.id"
          class="history-item"
          :class="{ active: run?.id === item.id }"
          @click="openRun(item.id)"
        >
          <span>{{ item.question }}</span
          ><small
            ><span :class="item.status === 'failed' ? 'red' : 'muted'">{{
              item.status === 'failed' ? t('failed') : date(item.created_at)
            }}</span>
            · {{ ms(item.timings_ms.total || 0) }}</small
          >
        </button>
      </div>
      <div class="sidebar-bottom">
        <span class="status-dot" />SQLite + Qdrant<small>{{ t('saved') }}</small>
      </div>
    </aside>

    <main class="main-workspace">
      <header class="app-header">
        <div>
          <span class="eyebrow">RAG DIAGNOSTICS</span>
          <h1>{{ t('workspace') }}</h1>
        </div>
        <div class="header-tools">
          <span v-for="(value, name) in health" :key="name" class="service-pill" :title="value"
            ><i class="status-dot" :class="{ failed: value !== 'ready' }" />{{ name
            }}<span v-if="value !== 'ready'">!</span></span
          >
          <select v-model="locale" aria-label="Language" @change="setLocale">
            <option value="zh-TW">繁體中文</option>
            <option value="en">English</option>
          </select>
        </div>
      </header>

      <div v-if="error" class="global-error" role="alert">
        {{ error }}<button aria-label="Dismiss error" @click="error = ''">×</button>
      </div>
      <div v-if="health.llm === 'model_missing'" class="global-error">{{ t('modelMissing') }}</div>

      <section class="query-panel">
        <div class="section-label">
          <span class="step-number">01</span>{{ t('question')
          }}<span class="model-label">{{ config?.llm.model || 'HTTP API' }}</span>
        </div>
        <form class="query-form" @submit.prevent="ask">
          <input
            v-model="question"
            :placeholder="t('placeholder')"
            aria-label="Question"
            maxlength="2000"
            :disabled="querying"
          />
          <button
            class="primary"
            :disabled="!question.trim() || document?.status !== 'ready' || querying"
            type="submit"
          >
            {{ querying ? t('asking') : t('ask') }} <span v-if="!querying">↗</span>
          </button>
        </form>
        <div class="query-options">
          <label
            >{{ t('topk') }}
            <input v-model.number="topK" type="number" min="1" max="12" aria-label="Top K"
          /></label>
          <label
            >{{ t('threshold') }}
            <input
              v-model.number="threshold"
              type="number"
              min="0"
              max="1"
              step="0.01"
              aria-label="Minimum score"
          /></label>
          <span class="mono tiny muted">dense · cosine</span>
          <button
            class="text-button example-button"
            type="button"
            @click="
              question =
                locale === 'en'
                  ? 'What is the maximum upload size for the Cedar trial?'
                  : 'Cedar 試用方案的上傳容量上限是多少？'
            "
          >
            {{ t('demoQuestion') }} ↗
          </button>
        </div>
      </section>

      <div class="inspection-grid">
        <section class="document-panel">
          <div class="panel-title">
            <span class="step-number">02</span>
            <div class="tabs">
              <button :class="{ active: view === 'pdf' }" @click="view = 'pdf'">
                {{ t('original') }}</button
              ><button :class="{ active: view === 'parsed' }" @click="loadChunks">
                {{ t('parsed') }}
              </button>
            </div>
            <span class="mono tiny muted">{{ document?.page_count || '—' }} {{ t('pages') }}</span>
          </div>
          <template v-if="document">
            <div class="document-bar">
              <strong>{{ document.filename }}</strong
              ><span class="badge" :class="document.status">{{ status(document.status) }}</span
              ><button
                class="text-button"
                :disabled="!['ready', 'failed'].includes(document.status)"
                @click="reindex"
              >
                {{ t('retry') }}
              </button>
            </div>
            <div v-if="document.error" class="error-box" role="alert">{{ document.error }}</div>
            <PdfViewer
              v-if="view === 'pdf'"
              :document-id="selectedId"
              :page="page"
              :provenance="provenance"
              :locale="locale"
              @page="page = $event"
            />
            <div v-else class="parsed-scroll">
              <div class="parsed-links">
                <a :href="`/api/documents/${selectedId}/parsed`" target="_blank">Markdown ↗</a
                ><a :href="`/api/documents/${selectedId}/parsed?format=json`" target="_blank"
                  >Docling JSON ↗</a
                >
              </div>
              <article v-for="chunk in parsedChunks" :key="chunk.id" class="parsed-chunk">
                <button class="text-button" @click="navigate(chunk)">
                  {{ t('source') }} · p. {{ chunk.pages.join(', ') }} ↗
                </button>
                <pre>{{ chunk.text }}</pre>
                <small class="mono muted">{{ chunk.id }} · {{ chunk.token_count }} tokens</small>
              </article>
            </div>
            <div class="document-footer">
              <span>{{ t('pdfHint') }}</span>
              <details>
                <summary>{{ t('documentDetails') }}</summary>
                <pre>{{ JSON.stringify(document, null, 2) }}</pre>
              </details>
            </div>
          </template>
          <div v-else class="empty-document">
            <div class="empty-graphic"><span>PDF</span><i /></div>
            <h2>{{ t('noDocs') }}</h2>
            <p>{{ t('noDocsHint') }}</p>
            <button class="primary" @click="fileInput?.click()">＋ {{ t('upload') }}</button
            ><a href="/api/sample.pdf" download="ragglass-field-guide.pdf">{{ t('sample') }} ↓</a>
          </div>
        </section>

        <section class="results-panel">
          <div class="panel-title">
            <span class="step-number">03</span><strong>{{ t('answer') }}</strong
            ><span class="mono tiny muted">{{ run ? run.id.slice(0, 8) : 'WAITING' }}</span>
          </div>
          <div v-if="!run" class="empty-results">
            <svg viewBox="0 0 80 80" width="72" fill="none">
              <rect x="12" y="18" width="40" height="46" rx="5" stroke="#b7c5be" stroke-width="2" />
              <path d="M22 30h20M22 38h13M22 46h15" stroke="#b7c5be" stroke-width="2" />
              <circle cx="52" cy="51" r="14" fill="#f5f8f6" stroke="#5c9e80" stroke-width="2" />
              <path d="m62 62 10 10" stroke="#5c9e80" stroke-width="3" />
            </svg>
            <h2>{{ t('noRun') }}</h2>
            <p>{{ t('noRunHint') }}</p>
            <span class="mono tiny">PDF → CHUNKS → EVIDENCE → ANSWER</span>
          </div>
          <div v-else class="results-scroll">
            <div v-if="run.error" class="error-box" role="alert">
              <strong>{{ run.error_code }}</strong>
              <p>{{ run.error }}</p>
            </div>
            <article v-if="run.answer" class="answer-card" data-testid="answer">
              <div class="answer-status">
                <span class="status-dot" :class="{ queued: !run.answerable }" />{{
                  run.answerable ? t('verified') : t('insufficient')
                }}<span class="mono">{{ run.settings.llm.model }}</span>
              </div>
              <p>{{ run.answer }}</p>
              <div class="citations">
                <template v-for="(citation, index) in run.citations" :key="citation.id"
                  ><button
                    v-for="p in citation.pages"
                    :key="p"
                    class="citation-button"
                    :data-chunk-id="citation.id"
                    @click="navigate(citation, p)"
                  >
                    [{{ index + 1 }}] {{ citation.filename }} · p. {{ p }} ↗
                  </button></template
                >
              </div>
            </article>
            <div class="evidence-heading">
              <h2>{{ t('evidence') }}</h2>
              <span>{{ run.evidence.length }} {{ t('chunks') }}</span>
            </div>
            <p v-if="!run.evidence.length" class="muted tiny">{{ t('noEvidence') }}</p>
            <button
              v-for="chunk in run.evidence"
              :key="chunk.id"
              class="evidence-card"
              :class="{ selected: selectedEvidence?.id === chunk.id }"
              :data-chunk-id="chunk.id"
              @click="navigate(chunk)"
            >
              <div class="evidence-card-top">
                <span class="rank">{{ String(chunk.rank).padStart(2, '0') }}</span
                ><strong>{{ chunk.filename }}</strong
                ><span class="score" :title="t('score')">{{ chunk.score.toFixed(3) }}</span>
              </div>
              <p>{{ chunk.text }}</p>
              <div class="evidence-meta">
                <span>p. {{ chunk.pages.join(', ') }} ↗</span
                ><span>{{ chunk.coordinates_available ? t('coords') : t('noCoords') }}</span>
              </div>
              <span class="chunk-id mono">{{ chunk.id }}</span>
            </button>
            <details class="run-details">
              <summary>{{ t('settings') }}</summary>
              <pre>{{
                JSON.stringify(
                  {
                    settings: run.settings,
                    documents: run.documents,
                    prompt: run.prompt,
                    raw_response: run.raw_response,
                    model_metrics: run.model_metrics,
                  },
                  null,
                  2,
                )
              }}</pre>
            </details>
            <button class="text-button download-run" @click="downloadRun">
              ↓ {{ t('download') }}
            </button>
          </div>
        </section>
      </div>

      <footer class="trace-panel">
        <div class="trace-label">
          <span class="trace-icon">⌁</span>{{ t('trace')
          }}<span class="mono tiny">{{ run?.status || 'IDLE' }}</span>
        </div>
        <div class="trace-stages">
          <template v-if="run"
            ><div
              v-for="(value, key) in run.timings_ms"
              :key="key"
              class="trace-stage"
              :class="{ total: key === 'total' }"
            >
              <span>{{ key }}</span
              ><strong class="mono">{{ ms(value) }}</strong>
            </div></template
          ><span v-else class="muted tiny"
            >embedding → retrieval → generation → citation validation</span
          >
        </div>
      </footer>
    </main>
  </div>
</template>
