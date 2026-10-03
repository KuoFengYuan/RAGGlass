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
    question: 'Query',
    placeholder: 'What is the maximum upload size for the Cedar trial?',
    ask: 'Retrieve & answer',
    asking: 'Retrieving & generating…',
    evidence: 'Retrieved evidence',
    answer: 'Document answer',
    noRun: 'No query results yet',
    noRunHint: 'Run a query to inspect the answer and its source evidence here.',
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
    library: 'Document library',
    inspect: 'Inspector',
    workbench: 'Workbench',
    retrieval: 'Retrieval',
    retrievalOptions: 'Retrieval options',
    pageIndex: 'Pages',
    record: 'Query record',
    filename: 'File',
    state: 'Status',
    opened: 'Uploaded',
    total: 'Total',
    completed: 'Completed',
    running: 'Running',
    generation: 'Generation',
    citation_validation: 'Citation validation',
    queryContext: 'Question in this record',
    evidenceHint: 'Select a passage to expand it and locate its source.',
    processing: 'Processing document',
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
    question: '查詢問題',
    placeholder: 'Cedar 試用方案的上傳容量上限是多少？',
    ask: '檢索並回答',
    asking: '正在檢索與生成…',
    evidence: '檢索證據',
    answer: '文件答案',
    noRun: '尚無查詢結果',
    noRunHint: '輸入問題後，這裡會列出本次答案與引用證據。',
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
    library: '文件庫',
    inspect: '檢視面板',
    workbench: '工作台',
    retrieval: '檢索',
    retrievalOptions: '檢索選項',
    pageIndex: '頁碼',
    record: '查詢紀錄',
    filename: '檔名',
    state: '狀態',
    opened: '上傳時間',
    total: '總耗時',
    completed: '已完成',
    running: '執行中',
    generation: '生成回答',
    citation_validation: '引用驗證',
    queryContext: '此紀錄的問題',
    evidenceHint: '點選片段可展開內容，並定位到原文。',
    processing: '正在處理文件',
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
const catalog = ref<HTMLDialogElement>()
const catalogMode = ref<'documents' | 'history'>('documents')
const servicesReady = computed(
  () => health.value.llm === 'ready' && health.value.qdrant === 'ready',
)
const retrievalValid = computed(
  () =>
    Number.isInteger(topK.value) &&
    topK.value >= 1 &&
    topK.value <= 12 &&
    Number.isFinite(threshold.value) &&
    threshold.value >= 0 &&
    threshold.value <= 1,
)
const thresholdLabel = computed(() =>
  Number.isFinite(threshold.value) ? threshold.value.toFixed(2) : '—',
)
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

function openCatalog(mode: 'documents' | 'history') {
  catalogMode.value = mode
  catalog.value?.showModal()
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
  catalog.value?.close()
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
  if (
    !question.value.trim() ||
    document.value?.status !== 'ready' ||
    !retrievalValid.value ||
    querying.value
  )
    return
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
    <input ref="fileInput" type="file" accept="application/pdf,.pdf" hidden @change="upload" />

    <header class="masthead">
      <a class="brand" href="/" aria-label="RAGGlass home">
        <svg class="brand-mark" viewBox="0 0 36 40" fill="none" aria-hidden="true">
          <path d="M18 2 34 11v18l-16 9-16-9V11L18 2Z" stroke="currentColor" stroke-width="1.5" />
          <path
            d="m2 11 16 9 16-9M18 20v18M10 6.5 26 16v18"
            stroke="currentColor"
            stroke-width="1.5"
          />
        </svg>
        <span>RAG<span class="brand-glass">Glass</span></span>
      </a>
      <nav class="main-nav" aria-label="Workspace navigation">
        <span class="nav-current">{{ t('workbench') }}</span>
        <button data-testid="open-library" @click="openCatalog('documents')">
          {{ t('library') }} <span>{{ docs.length }}</span>
        </button>
        <button data-testid="open-history" @click="openCatalog('history')">
          {{ t('history') }} <span>{{ runs.length }}</span>
        </button>
      </nav>
      <div class="header-tools">
        <details class="service-menu">
          <summary>
            <i class="status-dot" :class="{ failed: !servicesReady }" />{{ t('local') }}
          </summary>
          <div class="service-popover">
            <strong>{{ t('depends') }}</strong>
            <p v-for="(value, name) in health" :key="name">
              <span>{{ name }}</span
              ><span class="mono">{{ value }}</span>
            </p>
            <button class="text-button" @click="refresh">{{ t('reset') }}</button>
          </div>
        </details>
        <select v-model="locale" aria-label="Language" @change="setLocale">
          <option value="zh-TW">繁體中文</option>
          <option value="en">English</option>
        </select>
        <button class="upload-button" :disabled="uploading" @click="fileInput?.click()">
          <span>＋</span>{{ uploading ? '…' : t('upload') }}
        </button>
      </div>
    </header>

    <main class="main-workspace">
      <div class="workspace-heading">
        <div>
          <h1>{{ t('workspace') }}</h1>
          <p>See inside your RAG.</p>
        </div>
        <div class="document-switcher">
          <span class="file-icon">PDF</span>
          <select
            v-if="docs.length"
            :value="selectedId"
            :aria-label="t('selected')"
            @change="selectDocument(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="doc in docs" :key="doc.id" :value="doc.id">{{ doc.filename }}</option>
          </select>
          <span v-else class="muted">{{ t('noDocs') }}</span>
          <a class="sample-link" href="/api/sample.pdf" download="ragglass-field-guide.pdf"
            >↓ {{ t('sample') }}</a
          >
        </div>
      </div>

      <div v-if="error" class="global-error" role="alert">
        {{ error }}<button aria-label="Dismiss error" @click="error = ''">×</button>
      </div>
      <div v-if="health.llm === 'model_missing'" class="global-error" role="alert">
        {{ t('modelMissing') }}
      </div>

      <div class="inspection-grid">
        <section class="document-panel" :aria-label="t('original')">
          <div class="document-bar">
            <div class="tabs" role="tablist" :aria-label="t('source')">
              <button
                role="tab"
                :aria-selected="view === 'pdf'"
                :class="{ active: view === 'pdf' }"
                @click="view = 'pdf'"
              >
                {{ t('original') }}
              </button>
              <button
                role="tab"
                :aria-selected="view === 'parsed'"
                :class="{ active: view === 'parsed' }"
                @click="loadChunks"
              >
                {{ t('parsed') }}
              </button>
            </div>
            <span v-if="document" class="badge" :class="document.status"
              ><i class="status-dot" :class="document.status" />{{ status(document.status) }}</span
            >
            <button
              v-if="document"
              class="text-button reindex-button"
              :disabled="!['ready', 'failed'].includes(document.status)"
              @click="reindex"
            >
              ↻ {{ t('retry') }}
            </button>
          </div>

          <template v-if="document">
            <div v-if="document.error" class="error-box" role="alert">{{ document.error }}</div>
            <div class="reading-surface" v-if="view === 'pdf'">
              <nav class="page-index" :aria-label="t('pageIndex')">
                <span>{{ t('pageIndex') }}</span>
                <button
                  v-for="p in document.page_count"
                  :key="p"
                  :class="{ active: page === p, cited: selectedEvidence?.pages.includes(p) }"
                  :aria-label="`Page ${p}`"
                  :aria-current="page === p ? 'page' : undefined"
                  @click="page = p"
                >
                  <span class="page-outline"><i /><i /><i /></span
                  ><strong>{{ String(p).padStart(2, '0') }}</strong>
                </button>
              </nav>
              <PdfViewer
                :document-id="selectedId"
                :page="page"
                :provenance="provenance"
                :locale="locale"
                @page="page = $event"
              />
            </div>
            <div v-else class="parsed-scroll">
              <div class="parsed-links">
                <span>{{ document.chunk_count }} {{ t('chunks') }}</span
                ><a :href="`/api/documents/${selectedId}/parsed`" target="_blank" rel="noopener"
                  >Markdown ↗</a
                ><a
                  :href="`/api/documents/${selectedId}/parsed?format=json`"
                  target="_blank"
                  rel="noopener"
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
              <p>{{ t('pdfHint') }}</p>
              <details class="document-details">
                <summary>{{ t('documentDetails') }}</summary>
                <pre>{{ JSON.stringify(document, null, 2) }}</pre>
              </details>
            </div>
          </template>
          <div v-else class="empty-document">
            <div class="empty-page" aria-hidden="true"><span>PDF</span><i /><i /><i /></div>
            <h2>{{ t('noDocs') }}</h2>
            <p>{{ t('noDocsHint') }}</p>
            <button class="primary" @click="fileInput?.click()">＋ {{ t('upload') }}</button>
            <span class="upload-hint"
              >{{ t('uploadHint') }} {{ config?.max_upload_mb || 30 }} MB</span
            >
          </div>
        </section>

        <section class="results-panel" :aria-label="t('inspect')">
          <div class="inspector-heading">
            <span class="inspector-mark" aria-hidden="true">⌕</span>
            <h2>{{ t('inspect') }}</h2>
            <span class="mono">{{ run ? run.id.slice(0, 8) : '—' }}</span>
          </div>
          <section class="query-panel">
            <form class="query-form" @submit.prevent="ask">
              <label for="question">{{ t('question') }}</label>
              <textarea
                id="question"
                v-model="question"
                :placeholder="t('placeholder')"
                aria-label="Question"
                maxlength="2000"
                rows="2"
                :disabled="querying"
                @keydown.ctrl.enter.prevent="ask"
                @keydown.meta.enter.prevent="ask"
              />
              <div class="query-actions">
                <button
                  class="text-button example-button"
                  type="button"
                  @click="
                    question =
                      locale === 'en'
                        ? 'What is the maximum upload size for the Cedar pilot?'
                        : 'Cedar 試用方案的上傳容量上限是多少？'
                  "
                >
                  {{ t('demoQuestion') }}</button
                ><span class="keyboard-hint">⌘ / Ctrl ↵</span
                ><button
                  class="primary"
                  :disabled="
                    !question.trim() || document?.status !== 'ready' || !retrievalValid || querying
                  "
                  type="submit"
                >
                  {{ querying ? t('asking') : t('ask') }} <span v-if="!querying">→</span>
                </button>
              </div>
            </form>
            <details class="retrieval-options">
              <summary>
                {{ t('retrievalOptions')
                }}<span class="mono">K {{ topK }} · ≥ {{ thresholdLabel }}</span>
              </summary>
              <div class="query-options">
                <label
                  >{{ t('topk')
                  }}<input
                    v-model.number="topK"
                    type="number"
                    min="1"
                    max="12"
                    aria-label="Top K" /></label
                ><label
                  >{{ t('threshold')
                  }}<input
                    v-model.number="threshold"
                    type="number"
                    min="0"
                    max="1"
                    step="0.01"
                    aria-label="Minimum score"
                /></label>
              </div>
            </details>
          </section>

          <div v-if="!run" class="empty-results">
            <div class="empty-rule" />
            <h3>{{ t('noRun') }}</h3>
            <p>{{ t('noRunHint') }}</p>
            <dl>
              <div>
                <dt>{{ t('model') }}</dt>
                <dd class="mono">{{ config?.llm.model || '—' }}</dd>
              </div>
              <div>
                <dt>{{ t('source') }}</dt>
                <dd>
                  {{
                    document
                      ? `${document.page_count} ${t('pages')} / ${document.chunk_count} ${t('chunks')}`
                      : '—'
                  }}
                </dd>
              </div>
            </dl>
          </div>
          <div v-else class="results-scroll" aria-live="polite">
            <div class="run-context">
              <span>{{ t('queryContext') }}</span>
              <p>{{ run.question }}</p>
            </div>
            <div v-if="run.error" class="error-box" role="alert">
              <strong>{{ run.error_code }}</strong>
              <p>{{ run.error }}</p>
            </div>
            <article v-if="run.answer" class="answer-card" data-testid="answer">
              <div class="answer-heading">
                <h3>{{ t('answer') }}</h3>
                <span class="answer-status" :class="{ insufficient: !run.answerable }">{{
                  run.answerable ? t('verified') : t('insufficient')
                }}</span>
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
                    <span class="citation-number">{{ index + 1 }}</span
                    ><span>{{ citation.filename }} · p. {{ p }}</span
                    ><span>↗</span>
                  </button></template
                >
              </div>
              <span class="answer-model mono">{{ run.settings.llm.model }}</span>
            </article>
            <div class="evidence-heading">
              <h3>{{ t('evidence') }}</h3>
              <span class="mono">{{ String(run.evidence.length).padStart(2, '0') }}</span>
            </div>
            <p class="evidence-hint">
              {{ run.evidence.length ? t('evidenceHint') : t('noEvidence') }}
            </p>
            <ol class="evidence-list">
              <li v-for="chunk in run.evidence" :key="chunk.id">
                <button
                  class="evidence-card"
                  :class="{ selected: selectedEvidence?.id === chunk.id }"
                  :data-chunk-id="chunk.id"
                  :aria-expanded="selectedEvidence?.id === chunk.id"
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
              </li>
            </ol>
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
          <i class="status-dot" :class="{ queued: querying }" /><strong>{{ t('trace') }}</strong
          ><span>{{ querying ? t('running') : run ? status(run.status) : '—' }}</span>
        </div>
        <div class="trace-stages">
          <template v-if="run"
            ><div
              v-for="(value, key) in run.timings_ms"
              :key="key"
              class="trace-stage"
              :class="{ total: key === 'total' }"
            >
              <span>{{ status(String(key)) }}</span
              ><strong class="mono">{{ ms(value) }}</strong>
            </div></template
          ><span v-else class="muted"
            >{{ config?.llm.model }} <span class="trace-separator">/</span> {{ t('saved') }}</span
          >
        </div>
      </footer>
    </main>

    <dialog
      ref="catalog"
      class="catalog-dialog"
      aria-labelledby="catalog-title"
      @click="$event.target === catalog && catalog?.close()"
    >
      <div class="catalog-content">
        <header class="catalog-header">
          <div>
            <span class="catalog-kicker">RAGGlass / {{ t('local') }}</span>
            <h2 id="catalog-title">
              {{ catalogMode === 'documents' ? t('library') : t('history') }}
            </h2>
          </div>
          <button class="icon-button" :aria-label="t('close')" @click="catalog?.close()">×</button>
        </header>
        <template v-if="catalogMode === 'documents'"
          ><div class="catalog-actions">
            <p>{{ t('uploadHint') }} {{ config?.max_upload_mb || 30 }} MB</p>
            <button class="primary" :disabled="uploading" @click="fileInput?.click()">
              ＋ {{ t('upload') }}
            </button>
          </div>
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
                  >{{ doc.page_count }} {{ t('pages') }} · {{ doc.chunk_count }} {{ t('chunks') }} ·
                  {{ date(doc.created_at) }}</small
                ></span
              ><span class="badge" :class="doc.status">{{ status(doc.status) }}</span
              ><span>→</span>
            </button>
          </nav>
          <p v-if="!docs.length" class="catalog-empty">{{ t('noDocsHint') }}</p></template
        >
        <template v-else
          ><p v-if="!runs.length" class="catalog-empty">{{ t('noHistory') }}</p>
          <div class="history-list">
            <button
              v-for="item in runs"
              :key="item.id"
              class="history-item"
              :class="{ active: run?.id === item.id }"
              @click="openRun(item.id)"
            >
              <span class="history-time mono">{{ date(item.created_at) }}</span
              ><span class="history-question"
                >{{ item.question
                }}<small>{{ item.settings.llm.model }} · {{ status(item.status) }}</small></span
              ><span class="history-duration mono">{{
                item.timings_ms.total !== undefined ? ms(item.timings_ms.total) : '—'
              }}</span
              ><span>↗</span>
            </button>
          </div></template
        >
      </div>
    </dialog>
  </div>
</template>
