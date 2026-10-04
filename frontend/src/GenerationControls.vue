<script setup lang="ts">
import type { GenerationOptions } from './types'

const props = defineProps<{
  modelValue: GenerationOptions
  locale: string
  disabled: boolean
  valid: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: GenerationOptions] }>()
function update(key: keyof GenerationOptions, event: Event) {
  emit('update:modelValue', {
    ...props.modelValue,
    [key]: Number((event.target as HTMLInputElement).value),
  })
}
function preset(temperature: number) {
  emit('update:modelValue', { ...props.modelValue, temperature, top_p: 1 })
}
</script>

<template>
  <details class="generation-options" data-testid="generation-controls">
    <summary>
      {{ locale === 'en' ? 'Generation options' : '模型生成參數' }}
      <span class="mono">T {{ modelValue.temperature }} · P {{ modelValue.top_p }}</span>
    </summary>
    <div class="presets">
      <button type="button" class="text-button" :disabled="disabled" @click="preset(0)">
        {{ locale === 'en' ? 'Precise phrasing' : '精確表達' }}
      </button>
      <button type="button" class="text-button" :disabled="disabled" @click="preset(0.8)">
        {{ locale === 'en' ? 'Varied phrasing' : '多樣表達' }}
      </button>
    </div>
    <div class="query-options">
      <label>
        Temperature
        <input
          :value="modelValue.temperature"
          type="number"
          min="0"
          max="2"
          step="0.1"
          aria-label="Temperature"
          :disabled="disabled"
          @input="update('temperature', $event)"
        />
      </label>
      <label>
        Top-P
        <input
          :value="modelValue.top_p"
          type="number"
          min="0.01"
          max="1"
          step="0.05"
          aria-label="Top P"
          :disabled="disabled"
          @input="update('top_p', $event)"
        />
      </label>
      <label>
        {{ locale === 'en' ? 'Output token limit' : '輸出 token 上限' }}
        <input
          :value="modelValue.max_tokens"
          type="number"
          min="64"
          max="4096"
          step="64"
          aria-label="Output token limit"
          :disabled="disabled"
          @input="update('max_tokens', $event)"
        />
      </label>
    </div>
    <p class="control-hint">
      {{
        locale === 'en'
          ? 'Presets change phrasing; every answer still requires document evidence. Low temperature does not guarantee correct JSON or facts.'
          : '預設值只影響表達方式，答案仍需文件證據。低 Temperature 不保證 JSON 格式或事實正確。'
      }}
    </p>
    <p v-if="!valid" class="control-error" role="alert">
      {{
        locale === 'en'
          ? 'Check parameter ranges and leave context space for input.'
          : '請檢查參數範圍，並保留可用的輸入 context 空間。'
      }}
    </p>
  </details>
</template>

<style scoped>
.presets {
  display: flex;
  gap: 12px;
  margin-top: 10px;
}
.query-options {
  flex-wrap: wrap;
}
.control-hint,
.control-error {
  font-size: 12px;
  line-height: 1.6;
  margin: 10px 0;
}
.control-hint {
  color: var(--muted);
}
.control-error {
  color: #a42c2c;
}
</style>
