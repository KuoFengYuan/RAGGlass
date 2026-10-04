<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { api, ApiError } from './api'
import type { CleanupResult, Document, RunCatalog } from './types'

const props = defineProps<{
  documents: Document[]
  activeDocument: string
  activeRun?: string
  locale: string
  historyTotal: number
  revision: number
  uploading: boolean
  querying: boolean
  maxUpload: number
  maxPages: number
}>()
const emit = defineEmits<{
  select: [id: string]
  openRun: [id: string]
  upload: []
  cleaned: [result: CleanupResult]
}>()
const labels = {
  en: {
    local: 'Local workspace',
    library: 'Document library',
    history: 'Run history',
    close: 'Close',
    upload: 'Upload PDF',
    hint: 'Native-text PDF · up to',
    searchDocs: 'Search filenames',
    searchRuns: 'Search questions across all records',
    filter: 'Filter by status',
    allStatuses: 'All statuses',
    ready: 'Indexed',
    failed: 'Failed',
    delete_failed: 'Cleanup incomplete',
    processing: 'Processing',
    queued: 'Queued',
    parsing: 'Parsing',
    chunking: 'Chunking',
    embedding: 'Embedding',
    indexing: 'Indexing',
    deleting: 'Deleting',
    completed: 'Completed',
    running: 'Running',
    cancelled: 'Cancelled',
    pages: 'pages',
    chunks: 'chunks',
    delete: 'Delete',
    selected: 'selected',
    deleteSelected: 'Delete selected',
    clearAll: 'Clear all',
    selectVisible: 'Select this page',
    selectItem: 'Select',
    total: 'Total',
    matches: 'Matches',
    empty: 'No matching items.',
    emptyDocs: 'Upload a PDF to start tracing evidence.',
    emptyRuns: 'Your queries will appear here.',
    previous: 'Previous',
    next: 'Next',
    loading: 'Loading…',
    confirm: 'Confirm cleanup',
    cancel: 'Cancel',
    permanently: 'Delete permanently',
    noUndo: 'This cannot be undone.',
    documents: 'documents',
    runs: 'run records',
    allScope: 'All items in this workspace, including items hidden by filters or pagination.',
    selectedScope: 'Only the selected items listed below.',
    docsEffect:
      'Remove original PDFs, parse artifacts, chunks, and vectors. Saved run history remains and may contain document text; clear it separately. Source links for deleted PDFs will be disabled.',
    runsEffect:
      'Remove saved questions, answers, evidence, prompts, settings, and timings. PDFs and their indexes remain.',
    busyHint:
      'Processing documents and running queries must finish before their data can be deleted.',
    cleanup_busy: 'Selected data is processing or being queried. Wait for completion and retry.',
    workspace_busy: 'The workspace is updating. Try again shortly.',
    cleanup_count_changed:
      'The item count changed. Close this confirmation, refresh, and confirm the scope again.',
    cleanup_missing: 'Some items no longer exist. Refresh and select again.',
    cleanup_invalid_path: 'Unexpected document path. Check the backend storage directory.',
    cleanup_files_failed:
      'Local file cleanup failed. Check storage permissions and backend logs, then retry.',
    qdrant_cleanup_failed:
      'Vector removal could not be confirmed. Start Qdrant, check QDRANT_URL, then retry deletion. Local data is retained for retry.',
    partial: 'Some items could not be deleted. Review the error and retry those items.',
    sourceDeleted: 'Original PDF deleted',
  },
  'zh-TW': {
    local: '本機工作空間',
    library: '文件庫',
    history: '執行紀錄',
    close: '關閉',
    upload: '上傳 PDF',
    hint: '原生文字 PDF · 上限',
    searchDocs: '搜尋檔名',
    searchRuns: '搜尋所有紀錄的問題',
    filter: '依狀態篩選',
    allStatuses: '全部狀態',
    ready: '已索引',
    failed: '失敗',
    delete_failed: '清理未完成',
    processing: '處理中',
    queued: '等待處理',
    parsing: '解析中',
    chunking: '切塊中',
    embedding: '向量化中',
    indexing: '索引中',
    deleting: '刪除中',
    completed: '已完成',
    running: '執行中',
    cancelled: '已取消',
    pages: '頁',
    chunks: '片段',
    delete: '刪除',
    selected: '筆已選取',
    deleteSelected: '刪除所選',
    clearAll: '全部清空',
    selectVisible: '選取本頁',
    selectItem: '選取',
    total: '總數',
    matches: '符合條件',
    empty: '沒有符合條件的項目。',
    emptyDocs: '上傳 PDF，開始追查證據。',
    emptyRuns: '查詢後，執行紀錄會出現在這裡。',
    previous: '上一頁',
    next: '下一頁',
    loading: '載入中…',
    confirm: '確認清理',
    cancel: '取消',
    permanently: '永久刪除',
    noUndo: '此操作無法復原。',
    documents: '份文件',
    runs: '筆執行紀錄',
    allScope: '清理本機工作空間的全部項目，包含被篩選條件或分頁隱藏的資料。',
    selectedScope: '只清理下方列出的所選項目。',
    docsEffect:
      '移除原始 PDF、解析檔案、片段與向量。執行紀錄仍保留，可能含文件文字，需另外清理；已刪除 PDF 的來源連結會停用。',
    runsEffect: '移除已保存的問題、答案、證據、Prompt、設定與耗時。PDF 和索引仍保留。',
    busyHint: '文件處理或查詢中的資料，需等待完成後才能清理。',
    cleanup_busy: '所選資料正在處理或查詢，請等待完成後重試。',
    workspace_busy: '工作空間正在更新，請稍後重試。',
    cleanup_count_changed: '資料數量已變更，請關閉確認視窗、重新整理後再次確認清理範圍。',
    cleanup_missing: '部分項目已不存在，請重新整理後再次選取。',
    cleanup_invalid_path: '文件儲存路徑異常，請檢查後端儲存目錄。',
    cleanup_files_failed: '無法移除本機檔案，請檢查資料目錄權限與後端日誌後重試。',
    qdrant_cleanup_failed:
      '無法確認向量已清理，請啟動 Qdrant、檢查 QDRANT_URL 後重試刪除。本機資料保留供重試。',
    partial: '部分項目未能刪除，請查看錯誤並重試這些項目。',
    sourceDeleted: '原始 PDF 已刪除',
  },
}
type Label = keyof typeof labels.en
const t = (key: Label) => labels[props.locale === 'en' ? 'en' : 'zh-TW'][key]
const stateLabel = (value: string) => (value in labels.en ? t(value as Label) : value)
const dialog = ref<HTMLDialogElement>()
const confirmation = ref<HTMLDialogElement>()
const cancelButton = ref<HTMLButtonElement>()
const mode = ref<'documents' | 'history'>('documents')
const search = ref('')
const filter = ref('')
const selected = ref<string[]>([])
const offset = ref(0)
const history = ref<RunCatalog>({ items: [], total: 0, matched: 0, offset: 0, limit: 50 })
const loading = ref(false)
const clearing = ref(false)
const error = ref('')
const confirmError = ref('')
const plan = ref<{
  ids: string[]
  names: string[]
  all: boolean
  count: number
  kind: 'documents' | 'runs'
}>()
let requestNumber = 0
let debounce: ReturnType<typeof setTimeout>

const terminal = (doc: Document) =>
  ['ready', 'failed', 'cancelled', 'delete_failed'].includes(doc.status)
const visibleDocs = computed(() =>
  props.documents.filter(
    (doc) =>
      doc.filename.toLowerCase().includes(search.value.toLowerCase()) &&
      (!filter.value ||
        (filter.value === 'processing' ? !terminal(doc) : doc.status === filter.value)),
  ),
)
const visible = computed(() =>
  mode.value === 'documents' ? visibleDocs.value : history.value.items,
)
const selectable = computed(() =>
  mode.value === 'documents'
    ? visibleDocs.value.filter(terminal).map((doc) => doc.id)
    : history.value.items.filter((item) => item.status !== 'running').map((item) => item.id),
)
const total = computed(() =>
  mode.value === 'documents' ? props.documents.length : props.historyTotal,
)
const matched = computed(() =>
  mode.value === 'documents' ? visibleDocs.value.length : history.value.matched,
)
const allSelected = computed(
  () => selectable.value.length > 0 && selectable.value.every((id) => selected.value.includes(id)),
)
const blocked = computed(
  () => clearing.value || props.querying || (mode.value === 'history' && loading.value),
)
const formatDate = (value: string) =>
  new Date(value).toLocaleString(props.locale === 'en' ? 'en-US' : 'zh-TW', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
const ms = (value: number) =>
  value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value.toFixed(0)} ms`
const errorMessage = (e: unknown) => {
  const code = (e as ApiError).code
  return code in labels.en ? t(code as Label) : (e as Error).message
}

async function loadHistory() {
  const current = ++requestNumber
  loading.value = true
  try {
    const query = new URLSearchParams({
      search: search.value,
      status: filter.value,
      offset: String(offset.value),
      limit: '50',
    })
    const result = await api<RunCatalog>(`/runs/catalog?${query}`)
    if (current !== requestNumber) return
    if (offset.value && offset.value >= result.matched) {
      offset.value = Math.max(0, Math.ceil(result.matched / 50) - 1) * 50
      return loadHistory()
    }
    history.value = result
  } catch (e) {
    if (current === requestNumber) error.value = errorMessage(e)
  } finally {
    if (current === requestNumber) loading.value = false
  }
}

function open(target: 'documents' | 'history') {
  mode.value = target
  search.value = ''
  filter.value = ''
  selected.value = []
  offset.value = 0
  error.value = ''
  dialog.value?.showModal()
  if (target === 'history') void loadHistory()
}
function close() {
  dialog.value?.close()
}
defineExpose({ open, close })

function changePage(delta: number) {
  offset.value = Math.max(0, offset.value + delta * 50)
  selected.value = []
  void loadHistory()
}
function toggleVisible() {
  selected.value = allSelected.value ? [] : [...selectable.value]
}
async function confirmCleanup(ids: string[], all = false) {
  const names =
    mode.value === 'documents'
      ? props.documents.filter((doc) => ids.includes(doc.id)).map((doc) => doc.filename)
      : history.value.items.filter((item) => ids.includes(item.id)).map((item) => item.question)
  plan.value = {
    ids: [...ids],
    names,
    all,
    count: all ? total.value : ids.length,
    kind: mode.value === 'documents' ? 'documents' : 'runs',
  }
  confirmError.value = ''
  confirmation.value?.showModal()
  await nextTick()
  cancelButton.value?.focus()
}
async function cleanup() {
  if (!plan.value || clearing.value) return
  clearing.value = true
  confirmError.value = ''
  try {
    const result = await api<CleanupResult>(`/${plan.value.kind}/cleanup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(
        plan.value.all ? { all: true, expected_count: plan.value.count } : { ids: plan.value.ids },
      ),
    })
    confirmation.value?.close()
    selected.value = selected.value.filter((id) => !result.deleted_ids.includes(id))
    error.value = result.failures.length
      ? `${t('partial')} ${result.failures.map((item) => errorMessage({ code: item.code, message: item.message })).join(' ')}`
      : ''
    emit('cleaned', result)
    if (mode.value === 'history') await loadHistory()
  } catch (e) {
    confirmError.value = errorMessage(e)
  } finally {
    clearing.value = false
  }
}
watch([search, filter], () => {
  selected.value = []
  offset.value = 0
  clearTimeout(debounce)
  if (mode.value === 'history' && dialog.value?.open) debounce = setTimeout(loadHistory, 250)
})
watch(
  () => props.revision,
  () => {
    if (dialog.value?.open && mode.value === 'history' && !clearing.value) void loadHistory()
    if (mode.value === 'documents')
      selected.value = selected.value.filter((id) => props.documents.some((doc) => doc.id === id))
  },
)
onBeforeUnmount(() => {
  clearTimeout(debounce)
  requestNumber++
})
</script>

<template>
  <dialog
    ref="dialog"
    class="catalog-dialog"
    aria-labelledby="catalog-title"
    @click="$event.target === dialog && !clearing && close()"
  >
    <div class="catalog-content">
      <header class="catalog-header">
        <div>
          <span class="catalog-kicker">RAGGlass / {{ t('local') }}</span>
          <h2 id="catalog-title">{{ mode === 'documents' ? t('library') : t('history') }}</h2>
        </div>
        <button class="icon-button" :aria-label="t('close')" @click="close">×</button>
      </header>
      <div v-if="mode === 'documents'" class="catalog-actions">
        <p>{{ t('hint') }} {{ maxUpload }} MB · {{ maxPages }} {{ t('pages') }}</p>
        <button class="primary" :disabled="uploading || clearing" @click="emit('upload')">
          ＋ {{ t('upload') }}
        </button>
      </div>
      <div class="catalog-filters">
        <input
          v-model="search"
          type="search"
          maxlength="200"
          :placeholder="mode === 'documents' ? t('searchDocs') : t('searchRuns')"
          :aria-label="mode === 'documents' ? t('searchDocs') : t('searchRuns')"
        />
        <select v-model="filter" :aria-label="t('filter')">
          <option value="">{{ t('allStatuses') }}</option>
          <template v-if="mode === 'documents'">
            <option value="ready">{{ t('ready') }}</option>
            <option value="failed">{{ t('failed') }}</option>
            <option value="cancelled">{{ t('cancelled') }}</option>
            <option value="delete_failed">{{ t('delete_failed') }}</option>
            <option value="processing">{{ t('processing') }}</option>
          </template>
          <template v-else
            ><option value="completed">{{ t('completed') }}</option>
            <option value="failed">{{ t('failed') }}</option>
            <option value="running">{{ t('running') }}</option>
            <option value="cancelled">{{ t('cancelled') }}</option></template
          >
        </select>
      </div>
      <div class="cleanup-toolbar">
        <label
          ><input
            type="checkbox"
            :checked="allSelected"
            :disabled="!selectable.length || blocked"
            @change="toggleVisible"
          />{{ t('selectVisible') }}</label
        >
        <span>{{ selected.length }} {{ t('selected') }}</span>
        <button
          class="danger-button"
          :disabled="!selected.length || blocked"
          data-testid="delete-selected"
          @click="confirmCleanup(selected)"
        >
          {{ t('deleteSelected') }}
        </button>
        <button
          class="danger-button"
          :disabled="!total || blocked"
          data-testid="clear-all"
          @click="confirmCleanup([], true)"
        >
          {{ t('clearAll') }}
        </button>
      </div>
      <p class="catalog-summary">
        {{ t('total') }} {{ total }} · {{ t('matches') }} {{ matched
        }}<span v-if="loading"> · {{ t('loading') }}</span>
      </p>
      <p class="cleanup-hint">{{ t('busyHint') }}</p>
      <div v-if="error" class="error-box" role="alert">{{ error }}</div>
      <div v-if="mode === 'documents'" class="document-list" aria-label="Documents">
        <div v-for="doc in visibleDocs" :key="doc.id" class="catalog-row">
          <input
            v-model="selected"
            type="checkbox"
            :value="doc.id"
            :disabled="!terminal(doc) || blocked"
            :aria-label="`${t('selectItem')} ${doc.filename}`"
          />
          <button
            class="document-item"
            :class="{ active: activeDocument === doc.id }"
            @click="emit('select', doc.id)"
          >
            <span class="file-icon">PDF</span
            ><span class="document-text"
              ><strong>{{ doc.filename }}</strong>
              <small
                >{{ doc.page_count }} {{ t('pages') }} · {{ doc.chunk_count }} {{ t('chunks') }} ·
                {{ formatDate(doc.created_at) }}
                <template v-if="!terminal(doc) && doc.progress?.total_chunks">
                  · {{ doc.progress.indexed_chunks }} / {{ doc.progress.total_chunks }}
                </template></small
              ></span
            >
            <span class="badge" :class="doc.status">{{ stateLabel(doc.status) }}</span
            ><span>→</span>
          </button>
          <button
            class="danger-button row-delete"
            :aria-label="`${t('delete')} ${doc.filename}`"
            :disabled="!terminal(doc) || blocked"
            @click="confirmCleanup([doc.id])"
          >
            {{ t('delete') }}
          </button>
        </div>
      </div>
      <div v-else class="history-list">
        <div v-for="item in history.items" :key="item.id" class="catalog-row">
          <input
            v-model="selected"
            type="checkbox"
            :value="item.id"
            :disabled="item.status === 'running' || blocked"
            :aria-label="`${t('selectItem')} ${item.question}`"
          />
          <button
            class="history-item"
            :class="{ active: activeRun === item.id }"
            @click="emit('openRun', item.id)"
          >
            <span class="history-time mono">{{ formatDate(item.created_at) }}</span
            ><span class="history-question"
              >{{ item.question }}
              <small
                >{{ item.settings.llm.model }} · {{ stateLabel(item.status)
                }}<template v-if="item.missing_document_ids?.length">
                  · {{ t('sourceDeleted') }}</template
                ></small
              ></span
            >
            <span class="history-duration mono">{{
              item.timings_ms.total !== undefined ? ms(item.timings_ms.total) : '—'
            }}</span
            ><span>↗</span>
          </button>
          <button
            class="danger-button row-delete"
            :aria-label="`${t('delete')} ${item.question}`"
            :disabled="item.status === 'running' || blocked"
            @click="confirmCleanup([item.id])"
          >
            {{ t('delete') }}
          </button>
        </div>
      </div>
      <p v-if="!visible.length && !loading" class="catalog-empty">
        {{ total ? t('empty') : mode === 'documents' ? t('emptyDocs') : t('emptyRuns') }}
      </p>
      <div v-if="mode === 'history' && history.matched > 50" class="catalog-pagination">
        <button :disabled="!offset || loading" @click="changePage(-1)">{{ t('previous') }}</button>
        <span
          >{{ offset + 1 }}–{{ Math.min(offset + 50, history.matched) }} /
          {{ history.matched }}</span
        >
        <button :disabled="offset + 50 >= history.matched || loading" @click="changePage(1)">
          {{ t('next') }}
        </button>
      </div>
    </div>
  </dialog>
  <dialog
    ref="confirmation"
    class="cleanup-dialog"
    aria-labelledby="cleanup-title"
    aria-describedby="cleanup-scope cleanup-effect"
    @cancel="clearing && $event.preventDefault()"
  >
    <form @submit.prevent="cleanup">
      <h2 id="cleanup-title">{{ t('confirm') }}</h2>
      <p class="cleanup-count">
        {{ plan?.count }} {{ plan?.kind === 'documents' ? t('documents') : t('runs') }}
      </p>
      <p id="cleanup-scope">{{ plan?.all ? t('allScope') : t('selectedScope') }}</p>
      <ul v-if="!plan?.all" class="cleanup-names">
        <li v-for="(name, index) in plan?.names" :key="index">{{ name }}</li>
      </ul>
      <p id="cleanup-effect">
        {{ plan?.kind === 'documents' ? t('docsEffect') : t('runsEffect') }}
      </p>
      <strong class="cleanup-warning">{{ t('noUndo') }}</strong>
      <div v-if="confirmError" class="error-box" role="alert">{{ confirmError }}</div>
      <div class="cleanup-buttons">
        <button
          ref="cancelButton"
          type="button"
          :disabled="clearing"
          @click="confirmation?.close()"
        >
          {{ t('cancel') }}
        </button>
        <button
          type="submit"
          class="danger-primary"
          :disabled="clearing"
          data-testid="confirm-cleanup"
        >
          {{ clearing ? t('loading') : t('permanently') }}
        </button>
      </div>
    </form>
  </dialog>
</template>
