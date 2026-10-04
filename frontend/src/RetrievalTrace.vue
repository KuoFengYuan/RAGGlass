<script setup lang="ts">
import type { Run } from './types'
defineProps<{ run: Run; locale: string }>()
</script>

<template>
  <details v-if="run.retrieval_trace" class="retrieval-trace" data-testid="retrieval-trace">
    <summary>{{ locale === 'en' ? 'Retrieval rankings' : '檢索排名追蹤' }}</summary>
    <p v-if="run.retrieval_trace.complete === false" class="trace-hint">
      {{
        locale === 'en'
          ? 'Retrieval stopped before all methods finished; these rankings are partial.'
          : '檢索在所有方法完成前停止，此處保留的是部分排名。'
      }}
    </p>
    <p class="trace-hint">
      {{
        locale === 'en'
          ? 'Cosine and BM25 have different scales. Hybrid uses RRF ranks (k = 60), not raw score averages. Scores are not answer confidence.'
          : 'Cosine 與 BM25 分數尺度不同。混合檢索以 RRF 合併排名（k = 60），分數並非答案正確機率。'
      }}
    </p>
    <p v-if="run.retrieval_trace.mode === 'hybrid'" class="trace-hint">
      {{
        locale === 'en'
          ? 'Equal RRF scores use the higher BM25 score, then vector rank.'
          : 'RRF 同分時先比較 BM25 分數，再依向量排名排序。'
      }}
    </p>
    <p v-if="run.retrieval_trace.keyword_corpus" class="trace-hint">
      {{ locale === 'en' ? 'Keyword corpus: selected documents only' : '關鍵字統計僅涵蓋所選文件' }}
      · {{ run.retrieval_trace.keyword_corpus.corpus_chunks }}
      {{ locale === 'en' ? 'chunks' : '片段' }}
    </p>
    <div v-for="branch in ['dense', 'keyword'] as const" :key="branch" class="ranking-branch">
      <h4>
        {{ branch === 'dense' ? (locale === 'en' ? 'Vector · cosine' : '向量 · cosine') : 'BM25' }}
        · {{ run.retrieval_trace[branch].length }}
      </h4>
      <p v-if="!run.retrieval_trace[branch].length" class="trace-hint">
        {{
          locale === 'en'
            ? 'No candidates, or this branch was not used.'
            : '沒有候選片段，或本次未使用此檢索方式。'
        }}
      </p>
      <div v-else class="ranking-scroll">
        <table>
          <thead>
            <tr>
              <th>{{ locale === 'en' ? 'Rank' : '排名' }}</th>
              <th>{{ locale === 'en' ? 'Source / chunk' : '來源／片段' }}</th>
              <th>{{ branch === 'dense' ? 'Cosine' : 'BM25' }}</th>
              <th>{{ locale === 'en' ? 'Retrieved' : '納入證據' }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in run.retrieval_trace[branch]" :key="item.id">
              <td>{{ item.rank }}</td>
              <td>
                <span>{{ item.filename }} · p. {{ item.pages.join(', ') }}</span>
                <small class="mono" :title="item.id">{{ item.id.slice(0, 8) }}</small>
                <small v-if="item.matched_terms?.length">{{
                  item.matched_terms.join(' · ')
                }}</small>
              </td>
              <td class="mono">{{ item.score.toFixed(branch === 'dense' ? 3 : 4) }}</td>
              <td>{{ run.retrieval_trace.selected_ids.includes(item.id) ? '✓' : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </details>
</template>
