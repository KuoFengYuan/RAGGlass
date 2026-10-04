<script setup lang="ts">
import type { Run } from './types'
defineProps<{ run: Run; locale: string }>()
</script>

<template>
  <section
    v-if="run.context || run.attempts?.length"
    class="workflow-trace"
    data-testid="workflow-trace"
  >
    <h3>{{ locale === 'en' ? 'Context & model calls' : 'Context 與模型呼叫' }}</h3>
    <p class="trace-hint">
      {{
        locale === 'en'
          ? 'Preflight uses a conservative UTF-8 estimate, not E5 token counts. Native model usage below includes retries and summary steps when reported.'
          : '事前使用保守的 UTF-8 估算，並非 E5 token 數。下方模型實際回報用量涵蓋重試與摘要步驟。'
      }}
    </p>
    <dl v-if="run.context" class="budget-grid">
      <div>
        <dt>{{ locale === 'en' ? 'Estimated input' : '估算輸入' }}</dt>
        <dd>{{ run.context.estimated_input_tokens }}</dd>
      </div>
      <div>
        <dt>{{ locale === 'en' ? 'Input budget' : '輸入預算' }}</dt>
        <dd>{{ run.context.input_budget_tokens }}</dd>
      </div>
      <div>
        <dt>{{ locale === 'en' ? 'Output reserved' : '輸出保留' }}</dt>
        <dd>{{ run.context.reserved_output_tokens }}</dd>
      </div>
      <div>
        <dt>{{ locale === 'en' ? 'Chunks included / omitted' : '納入／排除片段' }}</dt>
        <dd>
          {{ run.context.selected_ids?.length || 0 }} / {{ run.context.omitted_ids?.length || 0 }}
        </dd>
      </div>
    </dl>
    <p v-if="run.context?.omitted_ids?.length" class="trace-hint">
      {{
        locale === 'en'
          ? 'Omitted chunks remain below for inspection; the model cannot cite them.'
          : '被排除的完整片段仍可在下方檢查，模型不能引用它們。'
      }}
    </p>
    <p v-if="run.usage" class="mono" data-testid="model-usage">
      {{ locale === 'en' ? 'Reported input / output' : '實際回報輸入／輸出' }}:
      {{ run.usage.reported_input_tokens }} / {{ run.usage.reported_output_tokens }} tokens ·
      {{ run.usage.reported_calls }} {{ locale === 'en' ? 'reported calls' : '次有回報呼叫' }}
      <span v-if="run.usage.unreported_calls">
        · {{ run.usage.unreported_calls }}
        {{ locale === 'en' ? 'calls with unknown usage' : '次用量未知' }}</span
      >
    </p>
    <ol class="attempt-list">
      <li v-for="(attempt, index) in run.attempts" :key="index">
        <details>
          <summary>
            <span class="mono">{{ attempt.node }} #{{ attempt.number }}</span>
            · {{ attempt.reason }} · {{ attempt.status }}
            <span v-if="attempt.elapsed_ms !== undefined">
              · {{ attempt.elapsed_ms.toFixed(0) }} ms</span
            >
            <strong v-if="attempt.error_code"> · {{ attempt.error_code }}</strong>
          </summary>
          <p v-if="attempt.context.actual_exceeds_reservation" class="trace-hint">
            {{
              locale === 'en'
                ? 'Native usage exceeded the preflight reservation. Review the model context configuration.'
                : '模型實際用量超過事前保留預算，請檢查模型 context 設定。'
            }}
          </p>
          <pre>{{ JSON.stringify(attempt, null, 2) }}</pre>
        </details>
      </li>
    </ol>
    <template v-if="run.workflow">
      <h4>{{ locale === 'en' ? 'Document summary steps' : '文件摘要步驟' }}</h4>
      <p class="trace-hint">
        {{ run.workflow.source_chunk_count }}
        {{ locale === 'en' ? 'source chunks' : '個原始片段' }} ·
        {{ run.workflow.map_batches || 0 }} {{ locale === 'en' ? 'map batches' : '個分段批次' }}
      </p>
      <details v-for="node in run.workflow.nodes" :key="node.id" class="summary-node">
        <summary>
          {{ node.id }} · {{ node.status }} · {{ node.source_ids.length }}
          {{ locale === 'en' ? 'sources' : '個來源' }}
        </summary>
        <pre>{{ JSON.stringify(node, null, 2) }}</pre>
      </details>
    </template>
  </section>
</template>

<style scoped>
.workflow-trace {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  margin: 16px 0;
}
.trace-hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--muted);
}
.budget-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  font-size: 12px;
}
.budget-grid dt {
  color: var(--muted);
}
.budget-grid dd {
  margin: 3px 0 0;
  font-family: monospace;
}
.attempt-list {
  padding-left: 20px;
  font-size: 12px;
}
.attempt-list li,
.summary-node {
  margin: 10px 0;
}
summary {
  cursor: pointer;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 11px;
  max-height: 320px;
  overflow: auto;
}
</style>
