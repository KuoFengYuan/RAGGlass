/** Guard public recordings against accidentally including private workspace data. */
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

export const root = new URL('../', import.meta.url)
export const fixturePath = fileURLToPath(new URL('examples/ragglass-field-guide.pdf', root))
export const sampleQuestion = 'What is the maximum upload size for the Cedar pilot?'
export const unknownQuestion = "What is the pilot's annual electricity cost in dollars?"

export async function publicWorkspace(baseURL) {
  const url = new URL(baseURL)
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) {
    throw new Error('Public capture requires a loopback application endpoint.')
  }
  const documentHash = createHash('sha256')
    .update(await readFile(fixturePath))
    .digest('hex')
  const allowed = new Set([
    ...JSON.parse(await readFile(new URL('examples/questions.json', root), 'utf8')).map(
      (item) => item.question,
    ),
    'Cedar 試用方案的上傳容量上限是多少？',
  ])
  const [documents, runs, config] = await Promise.all(
    ['/api/documents', '/api/runs?limit=10000', '/api/config'].map(async (path) => {
      const response = await fetch(new URL(path, baseURL))
      if (!response.ok) throw new Error(`Capture preflight failed: ${path} (${response.status})`)
      return response.json()
    }),
  )
  const ids = new Set(documents.map((item) => item.id))
  if (documents.length !== 1 || documents[0].status !== 'ready') {
    throw new Error('Upload the public fixture and wait for Indexed before recording.')
  }
  if (
    documents.some(
      (item) => item.hash !== documentHash || item.filename !== 'ragglass-field-guide.pdf',
    ) ||
    runs.length >= 500 ||
    runs.some((item) => !allowed.has(item.question) || item.document_ids.some((id) => !ids.has(id)))
  ) {
    throw new Error('Use a workspace containing only the public fixture and sample questions.')
  }
  const modelURL = new URL(config.llm.base_url)
  if (
    !['127.0.0.1', 'localhost', '[::1]'].includes(modelURL.hostname) ||
    modelURL.username ||
    modelURL.password ||
    modelURL.search
  ) {
    throw new Error(
      'Public capture requires a loopback model URL without credentials or query parameters.',
    )
  }
  return { documentHash, config }
}
