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
}
export interface Citation extends Omit<Evidence, 'text' | 'score' | 'rank' | 'token_count'> {}
export interface Run {
  id: string
  created_at: string
  status: string
  question: string
  document_ids: string[]
  answer: string | null
  answerable: boolean
  evidence: Evidence[]
  citations: Citation[]
  error: string | null
  error_code: string | null
  timings_ms: Record<string, number>
  settings: { llm: { model: string; provider: string }; [key: string]: unknown }
  prompt?: unknown
  documents?: unknown
  raw_response?: string
  model_metrics?: unknown
}
export interface Config {
  llm: { model: string; provider: string }
  embedding: { model: string }
  retrieval: { top_k: number; score_threshold: number }
  max_upload_mb: number
}
