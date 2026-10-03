<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  getDocument,
  GlobalWorkerOptions,
  type PDFDocumentProxy,
  type RenderTask,
} from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
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
const count = ref(0)
const width = ref(0)
const height = ref(0)
const busy = ref(false)
const error = ref('')
let pdf: PDFDocumentProxy | null = null
let task: RenderTask | null = null
let observer: ResizeObserver | null = null
let loadVersion = 0
let renderVersion = 0
let timer: ReturnType<typeof setTimeout> | undefined

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

async function render() {
  const version = ++renderVersion
  if (!pdf || !canvas.value || !container.value) return
  task?.cancel()
  busy.value = true
  error.value = ''
  try {
    const page = await pdf.getPage(Math.max(1, Math.min(props.page, pdf.numPages)))
    if (version !== renderVersion) return
    const base = page.getViewport({ scale: 1 })
    const scale = Math.min(Math.max(container.value.clientWidth - 48, 180) / base.width, 1.8)
    const viewport = page.getViewport({ scale })
    const ratio = window.devicePixelRatio || 1
    width.value = viewport.width
    height.value = viewport.height
    canvas.value.width = Math.floor(viewport.width * ratio)
    canvas.value.height = Math.floor(viewport.height * ratio)
    const context = canvas.value.getContext('2d')!
    task = page.render({
      canvas: canvas.value,
      canvasContext: context,
      viewport,
      transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined,
    })
    await task.promise
  } catch (e) {
    if ((e as Error).name !== 'RenderingCancelledException' && version === renderVersion) {
      error.value = (e as Error).message
    }
  } finally {
    if (version === renderVersion) busy.value = false
  }
}

watch(
  () => props.documentId,
  async (id) => {
    const version = ++loadVersion
    ++renderVersion
    task?.cancel()
    const old = pdf
    pdf = null
    void old?.destroy()
    error.value = ''
    count.value = 0
    busy.value = true
    try {
      const loaded = await getDocument({ url: `/api/documents/${id}/pdf` }).promise
      if (version !== loadVersion) {
        void loaded.destroy()
        return
      }
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
watch(() => props.page, render)
onMounted(() => {
  observer = new ResizeObserver(() => {
    clearTimeout(timer)
    timer = setTimeout(render, 120)
  })
  if (container.value) observer.observe(container.value)
})
onBeforeUnmount(() => {
  ++loadVersion
  ++renderVersion
  clearTimeout(timer)
  observer?.disconnect()
  task?.cancel()
  void pdf?.destroy()
})
</script>

<template>
  <div class="pdf-viewer">
    <div class="pdf-toolbar">
      <span class="mono muted"
        >PDF.js · {{ locale === 'en' ? 'Original document' : '原始文件' }}</span
      >
      <div class="page-controls">
        <button
          class="icon-button"
          :disabled="page <= 1"
          aria-label="Previous page"
          @click="emit('page', page - 1)"
        >
          ‹
        </button>
        <label class="page-counter"
          >{{ locale === 'en' ? 'Page' : '頁' }}
          <input
            aria-label="PDF page"
            type="number"
            :value="page"
            min="1"
            :max="count"
            @change="
              emit(
                'page',
                Math.max(1, Math.min(count, Number(($event.target as HTMLInputElement).value))),
              )
            "
          />
          / {{ count || '—' }}
        </label>
        <button
          class="icon-button"
          :disabled="page >= count"
          aria-label="Next page"
          @click="emit('page', page + 1)"
        >
          ›
        </button>
      </div>
      <a :href="`/api/documents/${documentId}/pdf`" target="_blank" rel="noopener">↗ PDF</a>
    </div>
    <div ref="container" class="pdf-scroll" data-testid="pdf-viewer" :data-page="page">
      <div v-if="error" class="error-box">
        {{ error }} —
        {{ locale === 'en' ? 'Try the PDF link above.' : '請使用上方 PDF 連結檢查原始文件。' }}
      </div>
      <div v-if="busy" class="pdf-loading">
        {{ locale === 'en' ? 'Rendering document…' : '正在顯示文件…' }}
      </div>
      <div class="pdf-paper" :style="{ width: `${width}px`, height: `${height}px` }">
        <canvas
          ref="canvas"
          :style="{ width: `${width}px`, height: `${height}px` }"
          aria-label="Original PDF page"
        />
        <div v-for="(box, i) in boxes" :key="i" class="evidence-box" :style="box" />
      </div>
    </div>
  </div>
</template>
