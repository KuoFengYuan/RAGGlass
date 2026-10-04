<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  getDocument,
  GlobalWorkerOptions,
  TextLayer,
  type PDFDocumentLoadingTask,
  type PDFDocumentProxy,
  type PDFPageProxy,
  type RenderTask,
} from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { findTextMatches, type PdfMatch } from './pdfSearch'
import type { Provenance } from './types'

GlobalWorkerOptions.workerSrc = workerUrl
const props = defineProps<{
  documentId: string
  page: number
  provenance: Provenance[]
  locale: string
}>()
const emit = defineEmits<{ page: [number] }>()
const container = ref<HTMLDivElement>()
const canvas = ref<HTMLCanvasElement>()
const textContainer = ref<HTMLDivElement>()
const searchInput = ref<HTMLInputElement>()
const count = ref(0)
const width = ref(0)
const height = ref(0)
const scale = ref(1)
const zoom = ref('fit')
const busy = ref(false)
const error = ref('')
const search = ref('')
const searching = ref(false)
const searchError = ref('')
const matches = ref<PdfMatch[]>([])
const matchIndex = ref(0)
let pdf: PDFDocumentProxy | null = null
let loadingTask: PDFDocumentLoadingTask | null = null
let task: RenderTask | null = null
let textLayer: TextLayer | null = null
let observer: ResizeObserver | null = null
let loadVersion = 0
let renderVersion = 0
let searchVersion = 0
let resizeTimer: ReturnType<typeof setTimeout> | undefined
let searchTimer: ReturnType<typeof setTimeout> | undefined
type TextContent = Awaited<ReturnType<PDFPageProxy['getTextContent']>>
const textCache = new Map<number, TextContent>()
const en = computed(() => props.locale === 'en')
const currentMatch = computed(() => matches.value[matchIndex.value])
const boxes = computed(() =>
  props.provenance
    .filter((p) => p.page === props.page && p.bbox)
    .map((p) => {
      const b = p.bbox!
      const bottom = b.coord_origin.toUpperCase().includes('BOTTOM')
      return {
        left: `${(Math.min(b.l, b.r) / p.page_width) * 100}%`,
        top: `${((bottom ? p.page_height - Math.max(b.t, b.b) : Math.min(b.t, b.b)) / p.page_height) * 100}%`,
        width: `${(Math.abs(b.r - b.l) / p.page_width) * 100}%`,
        height: `${(Math.abs(b.t - b.b) / p.page_height) * 100}%`,
      }
    }),
)

async function pageText(document: PDFDocumentProxy, number: number, version: number) {
  const cached = textCache.get(number)
  if (cached) return cached
  const page = await document.getPage(number)
  const content = await page.getTextContent()
  if (version === loadVersion) textCache.set(number, content)
  return content
}

function highlightMatches(scroll = false) {
  if (!textLayer) return
  const layer = textLayer
  const ranges = matches.value.flatMap((match, index) =>
    match.page === props.page
      ? match.ranges.map((range) => ({ ...range, active: index === matchIndex.value }))
      : [],
  )
  layer.textDivs.forEach((div, index) => {
    const text = layer.textContentItemsStr[index] || ''
    const fragment = window.document.createDocumentFragment()
    let offset = 0
    for (const range of ranges.filter((range) => range.item === index)) {
      fragment.append(window.document.createTextNode(text.slice(offset, range.start)))
      const mark = window.document.createElement('mark')
      mark.className = `pdf-search-hit${range.active ? ' active' : ''}`
      mark.textContent = text.slice(range.start, range.end)
      fragment.append(mark)
      offset = range.end
    }
    fragment.append(window.document.createTextNode(text.slice(offset)))
    div.replaceChildren(fragment)
  })
  if (scroll) {
    textContainer.value
      ?.querySelector('.pdf-search-hit.active')
      ?.scrollIntoView({ block: 'center', inline: 'nearest' })
  }
}

async function render() {
  const version = ++renderVersion
  const document = pdf
  if (!document || !canvas.value || !container.value || !textContainer.value) return
  task?.cancel()
  textLayer?.cancel()
  textLayer = null
  textContainer.value.replaceChildren()
  busy.value = true
  error.value = ''
  try {
    const page = await document.getPage(Math.max(1, Math.min(props.page, document.numPages)))
    if (version !== renderVersion) return
    const base = page.getViewport({ scale: 1 })
    scale.value =
      zoom.value === 'fit'
        ? Math.min(Math.max(container.value.clientWidth - 48, 180) / base.width, 1.8)
        : Number(zoom.value)
    const viewport = page.getViewport({ scale: scale.value })
    const textScale = viewport.scale * viewport.userUnit
    const ratio = window.devicePixelRatio || 1
    width.value = viewport.width
    height.value = viewport.height
    canvas.value.width = Math.floor(viewport.width * ratio)
    canvas.value.height = Math.floor(viewport.height * ratio)
    const context = canvas.value.getContext('2d')!
    const rendering = page.render({
      canvas: canvas.value,
      canvasContext: context,
      viewport,
      transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined,
    })
    task = rendering
    await rendering.promise
    const content = await pageText(document, props.page, loadVersion)
    if (version !== renderVersion) return
    await nextTick()
    const layer = new TextLayer({
      textContentSource: content,
      container: textContainer.value!,
      viewport,
    })
    textContainer.value!.style.setProperty('--total-scale-factor', String(textScale))
    textLayer = layer
    await layer.render()
    if (version === renderVersion) highlightMatches(currentMatch.value?.page === props.page)
  } catch (e) {
    if ((e as Error).name !== 'RenderingCancelledException' && version === renderVersion) {
      error.value = (e as Error).message
    }
  } finally {
    if (version === renderVersion) busy.value = false
  }
}

async function find() {
  const version = ++searchVersion
  const document = pdf
  const query = search.value.trim()
  matches.value = []
  matchIndex.value = 0
  searchError.value = ''
  highlightMatches()
  if (!document || !query) {
    searching.value = false
    return
  }
  searching.value = true
  const documentVersion = loadVersion
  const found: PdfMatch[] = []
  try {
    for (let number = 1; number <= document.numPages; number++) {
      const content = await pageText(document, number, documentVersion)
      if (version !== searchVersion || documentVersion !== loadVersion) return
      const items = content.items.flatMap((item) => ('str' in item ? [item.str] : []))
      found.push(...findTextMatches(items, query).map((ranges) => ({ page: number, ranges })))
    }
    if (version !== searchVersion) return
    matches.value = found
    if (found.length) goToMatch(0)
  } catch {
    if (version === searchVersion) {
      searchError.value = en.value ? 'PDF text could not be searched.' : '無法搜尋此 PDF 的文字。'
    }
  } finally {
    if (version === searchVersion) searching.value = false
  }
}

function goToMatch(index: number) {
  if (!matches.value.length) return
  matchIndex.value = (index + matches.value.length) % matches.value.length
  const match = currentMatch.value!
  if (match.page !== props.page) emit('page', match.page)
  else highlightMatches(true)
}

function searchKey(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'f') {
    event.preventDefault()
    searchInput.value?.focus()
    searchInput.value?.select()
  }
}

watch(
  () => props.documentId,
  async (id) => {
    const version = ++loadVersion
    ++renderVersion
    ++searchVersion
    clearTimeout(searchTimer)
    task?.cancel()
    textLayer?.cancel()
    textLayer = null
    const old = loadingTask
    loadingTask = null
    pdf = null
    void old?.destroy()
    textCache.clear()
    matches.value = []
    search.value = ''
    searching.value = false
    zoom.value = 'fit'
    error.value = ''
    count.value = 0
    busy.value = true
    try {
      const loading = getDocument({ url: `/api/documents/${id}/pdf`, isEvalSupported: false })
      loadingTask = loading
      const loaded = await loading.promise
      if (version !== loadVersion) return
      pdf = loaded
      count.value = loaded.numPages
      await nextTick()
      await render()
    } catch (e) {
      if (version === loadVersion) {
        error.value = (e as Error).message
        busy.value = false
      }
    }
  },
  { immediate: true },
)
watch([() => props.page, zoom], render)
watch(search, () => {
  ++searchVersion
  clearTimeout(searchTimer)
  matches.value = []
  matchIndex.value = 0
  searchError.value = ''
  highlightMatches()
  searching.value = !!search.value.trim()
  searchTimer = setTimeout(find, 250)
})
onMounted(() => {
  observer = new ResizeObserver(() => {
    clearTimeout(resizeTimer)
    resizeTimer = setTimeout(render, 120)
  })
  if (container.value) observer.observe(container.value)
})
onBeforeUnmount(() => {
  ++loadVersion
  ++renderVersion
  ++searchVersion
  clearTimeout(resizeTimer)
  clearTimeout(searchTimer)
  observer?.disconnect()
  task?.cancel()
  textLayer?.cancel()
  void loadingTask?.destroy()
})
</script>

<template>
  <div class="pdf-viewer" @keydown="searchKey">
    <div class="pdf-toolbar">
      <div class="page-controls">
        <button
          class="icon-button"
          :disabled="page <= 1"
          :aria-label="en ? 'Previous page' : '上一頁'"
          @click="emit('page', page - 1)"
        >
          ‹
        </button>
        <label class="page-counter">
          {{ en ? 'Page' : '頁' }}
          <input
            :aria-label="en ? 'PDF page' : 'PDF 頁碼'"
            type="number"
            :value="page"
            min="1"
            :max="count"
            @change="
              emit(
                'page',
                Math.max(
                  1,
                  Math.min(count, Number(($event.target as HTMLInputElement).value) || 1),
                ),
              )
            "
          />
          / {{ count || '—' }}
        </label>
        <button
          class="icon-button"
          :disabled="!count || page >= count"
          :aria-label="en ? 'Next page' : '下一頁'"
          @click="emit('page', page + 1)"
        >
          ›
        </button>
      </div>
      <label class="pdf-zoom">
        {{ en ? 'Zoom' : '縮放' }}
        <select v-model="zoom" :aria-label="en ? 'PDF zoom' : 'PDF 縮放'">
          <option value="fit">{{ en ? 'Fit width' : '符合寬度' }}</option>
          <option
            v-for="value in [0.5, 0.75, 1, 1.25, 1.5, 2, 3]"
            :key="value"
            :value="String(value)"
          >
            {{ value * 100 }}%
          </option>
        </select>
      </label>
      <a :href="`/api/documents/${documentId}/pdf`" target="_blank" rel="noopener">↗ PDF</a>
    </div>
    <form class="pdf-search" @submit.prevent="goToMatch(matchIndex + 1)">
      <input
        ref="searchInput"
        v-model="search"
        type="search"
        maxlength="120"
        :aria-label="en ? 'Search PDF text' : '搜尋 PDF 文字'"
        :placeholder="en ? 'Search this PDF…' : '搜尋這份 PDF…'"
        @keydown.esc.prevent="search = ''"
        @keydown.shift.enter.prevent="goToMatch(matchIndex - 1)"
      />
      <span class="pdf-search-count" role="status" aria-live="polite">
        {{
          searching
            ? en
              ? 'Searching…'
              : '搜尋中…'
            : searchError ||
              (search.trim()
                ? matches.length
                  ? `${matchIndex + 1} / ${matches.length}`
                  : en
                    ? 'No matches'
                    : '找不到符合文字'
                : '')
        }}
      </span>
      <button
        type="button"
        class="icon-button"
        :disabled="!matches.length || searching"
        :aria-label="en ? 'Previous match' : '上一個搜尋結果'"
        @click="goToMatch(matchIndex - 1)"
      >
        ‹
      </button>
      <button
        type="submit"
        class="icon-button"
        :disabled="!matches.length || searching"
        :aria-label="en ? 'Next match' : '下一個搜尋結果'"
      >
        ›
      </button>
    </form>
    <div
      ref="container"
      class="pdf-scroll"
      data-testid="pdf-viewer"
      :data-page="page"
      :data-zoom="zoom"
      tabindex="0"
      :aria-label="en ? 'PDF reading area' : 'PDF 閱讀區域'"
    >
      <div v-if="error" class="error-box" role="alert">
        {{ error }} — {{ en ? 'Try the PDF link above.' : '請使用上方 PDF 連結檢查原始文件。' }}
      </div>
      <div v-if="busy" class="pdf-loading">{{ en ? 'Rendering document…' : '正在顯示文件…' }}</div>
      <div
        class="pdf-paper"
        :style="{
          width: `${width}px`,
          height: `${height}px`,
          '--total-scale-factor': scale,
          '--scale-round-x': '1px',
          '--scale-round-y': '1px',
        }"
      >
        <canvas
          ref="canvas"
          :style="{ width: `${width}px`, height: `${height}px` }"
          :aria-label="en ? 'Original PDF page' : '原始 PDF 頁面'"
        />
        <div v-for="(box, i) in boxes" :key="i" class="evidence-box" :style="box" />
        <div
          ref="textContainer"
          class="pdf-text-layer"
          :aria-label="en ? 'Selectable PDF text' : '可選取的 PDF 文字'"
        />
      </div>
    </div>
  </div>
</template>
