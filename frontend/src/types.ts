export interface Box {
  l: number
  t: number
  r: number
  b: number
  coord_origin: string
}
export interface Provenance {
  page: number
  bbox: Box | null
  page_width: number
  page_height: number
  item_ref: string
}
export interface Document {
  id: string
  hash: string
  filename: string
  status: string
  page_count: number
  chunk_count: number
  error: string | null
  created_at: string
  timings_ms: Record<string, number>
  parser: unknown
  chunking: unknown
  embedding: unknown
  queued_at?: string
  processing_started_at?: string | null
  finished_at?: string | null
  cancel_requested?: boolean
  progress?: { total_chunks: number | null; embedded_chunks: number; indexed_chunks: number }
}
export interface Evidence {
  id: string
  document_id: string
  document_hash: string
  filename: string
  page: number
  pages: number[]
  text: string
  score: number
  rank: number
  token_count: number
  provenance: Provenance[]
  coordinates_available: boolean
  coordinate_scope: string
  source_available?: boolean
  score_kind?: 'cosine' | 'bm25' | 'rrf'
  retrieval_scores?: Partial<Record<'dense' | 'keyword', { rank: number; score: number }>>
  matched_terms?: string[]
}
export type RetrievalMode = 'dense' | 'keyword' | 'hybrid'
export interface RetrievalSettings {
  mode?: RetrievalMode
  strategy?: string
  top_k?: number
  score_threshold?: number
  candidate_k?: number
}
export interface RetrievalCandidate {
  id: string
  document_id: string
  filename: string
  pages: number[]
  rank: number
  score: number
  matched_terms?: string[]
}
export interface Citation extends Omit<Evidence, 'text' | 'score' | 'rank' | 'token_count'> {}
export interface GenerationOptions {
  temperature: number
  top_p: number
  max_tokens: number
}
export interface ContextReport {
  estimated_input_tokens: number
  input_budget_tokens: number
  context_tokens: number
  reserved_output_tokens: number
  safety_margin_tokens: number
  selected_ids?: string[]
  omitted_ids?: string[]
  actual_input_tokens?: number
  actual_output_tokens?: number
  actual_exceeds_reservation?: boolean
}
export interface ModelAttempt {
  node: string
  number: number
  reason: string
  status: string
  error_code?: string
  elapsed_ms?: number
  context: ContextReport
  prompt?: unknown
  raw_response?: string
  model_metrics?: unknown
}
export interface WorkflowNode {
  id: string
  phase: string
  level: number
  status: string
  source_ids: string[]
  elapsed_ms?: number
  context: ContextReport
  prompt?: unknown
  output?: unknown
}
export interface Run {
  id: string
  created_at: string
  status: string
  kind?: 'query' | 'summary'
  question: string
  stage?: string
  stage_started_at?: string
  cancel_requested?: boolean
  finished_at?: string
  document_ids: string[]
  answer: string | null
  answerable: boolean
  evidence: Evidence[]
  citations: Citation[]
  error: string | null
  error_code: string | null
  timings_ms: Record<string, number>
  settings: {
    llm: { model: string; provider: string } & Partial<GenerationOptions>
    retrieval?: RetrievalSettings
    [key: string]: unknown
  }
  context?: ContextReport
  attempts?: ModelAttempt[]
  usage?: {
    reported_input_tokens: number
    reported_output_tokens: number
    reported_calls: number
    unreported_calls: number
  }
  workflow?: { nodes: WorkflowNode[]; source_chunk_count: number; map_batches?: number }
  summary_points?: { text: string; citation_ids: string[] }[]
  prompt?: unknown
  documents?: unknown
  raw_response?: string
  model_metrics?: unknown
  missing_document_ids?: string[]
  retrieval_trace?: {
    mode: RetrievalMode
    dense: RetrievalCandidate[]
    keyword: RetrievalCandidate[]
    selected_ids: string[]
    complete?: boolean
    keyword_corpus?: { query_terms: string[]; corpus_chunks: number; average_chunk_terms: number }
  }
}
export interface RunCatalog {
  items: Run[]
  total: number
  matched: number
  offset: number
  limit: number
}
export interface CleanupResult {
  kind: 'documents' | 'runs'
  deleted_ids: string[]
  failures: { id: string; code: string; message: string }[]
}
export interface Config {
  llm: { model: string; provider: string; context_tokens?: number } & Partial<GenerationOptions>
  embedding: { model: string }
  retrieval: { top_k: number; score_threshold: number; mode?: RetrievalMode; candidate_k?: number }
  max_upload_mb: number
  max_pdf_pages: number
  workflow?: { context_margin_tokens: number; max_calls: number; timeout_seconds: number }
}
