<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { api } from './api'
import type { Document } from './types'

const props = defineProps<{ document: Document; locale: string }>()
const emit = defineEmits<{ refresh: []; error: [message: string] }>()
const stopping = ref(false)
const clock = ref(Date.now())
const timer = setInterval(() => (clock.value = Date.now()), 500)
onBeforeUnmount(() => clearInterval(timer))
const en = computed(() => props.locale === 'en')
const active = computed(() =>
  ['queued', 'parsing', 'chunking', 'embedding', 'indexing'].includes(props.document.status),
)
const progress = computed(() => props.document.progress)
const elapsed = computed(() => {
  const started = props.document.processing_started_at || props.document.queued_at
  const end = props.document.finished_at ? Date.parse(props.document.finished_at) : clock.value
  return started ? Math.max(0, (end - Date.parse(started)) / 1000).toFixed(1) : null
})
const stage = computed(() => {
  const labels: Record<string, [string, string]> = {
    queued: ['等待處理', 'Queued'],
    parsing: ['解析中', 'Parsing'],
    chunking: ['切塊中', 'Chunking'],
    embedding: ['向量化中', 'Embedding'],
    indexing: ['索引中', 'Indexing'],
    ready: ['已索引', 'Indexed'],
    failed: ['處理失敗', 'Processing failed'],
    cancelled: ['處理已停止', 'Processing stopped'],
  }
  return labels[props.document.status]?.[en.value ? 1 : 0] || props.document.status
})
async function stop() {
  if (stopping.value || props.document.cancel_requested) return
  stopping.value = true
  try {
    await api(`/documents/${props.document.id}/cancel`, { method: 'POST' })
    emit('refresh')
  } catch (error) {
    emit('error', (error as Error).message)
  } finally {
    stopping.value = false
  }
}
</script>

<template>
  <div
    v-if="active || document.status === 'cancelled' || (document.status === 'failed' && progress)"
    class="document-progress"
    data-testid="document-progress"
  >
    <div class="document-progress-heading">
      <strong role="status">{{ stage }}</strong>
      <span v-if="elapsed !== null" class="mono">
        {{ document.status === 'queued' ? (en ? 'Waiting' : '已等待') : en ? 'Elapsed' : '耗時' }}
        {{ elapsed }} s
      </span>
      <button
        v-if="active"
        class="text-button"
        :disabled="stopping || document.cancel_requested"
        @click="stop"
      >
        {{
          stopping || document.cancel_requested
            ? en
              ? 'Stopping…'
              : '正在停止…'
            : en
              ? 'Stop processing'
              : '停止處理'
        }}
      </button>
    </div>
    <template v-if="progress?.total_chunks">
      <progress
        :value="progress.indexed_chunks"
        :max="progress.total_chunks"
        :aria-label="en ? 'Chunks written to index' : '已寫入索引片段'"
      />
      <p>
        {{ en ? 'Embedded' : '已向量化' }} {{ progress.embedded_chunks }} /
        {{ progress.total_chunks }} · {{ en ? 'Indexed' : '已寫入索引' }}
        {{ progress.indexed_chunks }} / {{ progress.total_chunks }}
        {{ en ? 'chunks' : '片段' }}
      </p>
    </template>
    <p v-if="active && document.cancel_requested">
      {{ en ? 'Finishing the current operation, then stopping.' : '等待目前操作完成後停止。' }}
    </p>
    <p v-else-if="document.status === 'cancelled'">
      {{
        en
          ? 'Original PDF and completed artifacts are retained. Reindex to process again.'
          : '原始 PDF 與已完成產物仍保留；可重新索引再處理。'
      }}
    </p>
    <p v-else-if="active && !progress?.total_chunks">
      {{
        en
          ? 'Chunk counts appear after parsing. You can keep reading the original PDF.'
          : '解析與切塊完成後會顯示片段進度；等待時仍可閱讀原始 PDF。'
      }}
    </p>
  </div>
</template>
