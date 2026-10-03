/** Synthetic HTTP contracts for publication guards; these do not simulate model inference. */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { fixturePath, publicWorkspace, sampleQuestion } from '../scripts/public_fixture.mjs'

const hash = createHash('sha256')
  .update(await readFile(fixturePath))
  .digest('hex')
const document = {
  id: 'public-fixture',
  hash,
  filename: 'ragglass-field-guide.pdf',
  status: 'ready',
}

async function workspace(overrides, verify) {
  const routes = {
    '/api/documents': [document],
    '/api/runs': [{ question: sampleQuestion, document_ids: [document.id] }],
    '/api/config': { llm: { base_url: 'http://127.0.0.1:11434' } },
    ...overrides,
  }
  const server = createServer((request, response) => {
    response.setHeader('Content-Type', 'application/json')
    response.end(JSON.stringify(routes[new URL(request.url, 'http://localhost').pathname]))
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  try {
    await verify(`http://127.0.0.1:${server.address().port}`)
  } finally {
    server.closeAllConnections()
    await new Promise((resolve) => server.close(resolve))
  }
}

test('publication guard accepts an indexed public fixture workspace', async () => {
  await workspace({}, async (url) => assert.equal((await publicWorkspace(url)).documentHash, hash))
})

for (const [name, overrides, message] of [
  [
    'private PDF',
    { '/api/documents': [{ ...document, hash: 'private-document' }] },
    /only the public fixture/,
  ],
  [
    'private question',
    { '/api/runs': [{ question: 'Private customer data', document_ids: [document.id] }] },
    /only the public fixture/,
  ],
  [
    'truncated history',
    {
      '/api/runs': Array.from({ length: 500 }, () => ({
        question: sampleQuestion,
        document_ids: [document.id],
      })),
    },
    /only the public fixture/,
  ],
  [
    'unindexed fixture',
    { '/api/documents': [{ ...document, status: 'parsing' }] },
    /wait for Indexed/,
  ],
  [
    'model URL credentials',
    { '/api/config': { llm: { base_url: 'http://user:example-secret@127.0.0.1:11434' } } },
    /without credentials/,
  ],
]) {
  test(`publication guard refuses ${name}`, async () => {
    await workspace(overrides, (url) => assert.rejects(publicWorkspace(url), message))
  })
}

test('publication guard refuses a non-loopback application before any request', async () => {
  await assert.rejects(publicWorkspace('https://example.invalid'), /loopback application/)
})
