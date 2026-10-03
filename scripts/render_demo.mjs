/** Re-caption existing real footage; does not query or modify the RAG application. */
import { readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { exportDemoMedia, localMediaDirectory, mediaRoot } from './demo_media.mjs'

const sourcePath = new URL('docs/media/demo-recording.json', mediaRoot)
const sourceBytes = await readFile(sourcePath)
const recording = JSON.parse(sourceBytes)
if (recording.mock || recording.playback_speed !== 1)
  throw new Error('Expected actual footage at normal speed.')
const rawBytes = await readFile(`${localMediaDirectory}/live-recording.webm`)
const rendererBytes = await readFile(new URL('scripts/demo_media.mjs', mediaRoot))
const media = await exportDemoMedia(
  recording,
  localMediaDirectory,
  fileURLToPath(new URL('docs/images/', mediaRoot)),
)
const report = {
  rendered_at: new Date().toISOString(),
  workspace_base_commit: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
  renderer_sha256: createHash('sha256').update(rendererBytes).digest('hex'),
  source_recording: 'demo-recording.json',
  source_recording_sha256: createHash('sha256').update(sourceBytes).digest('hex'),
  raw_recording_sha256: createHash('sha256').update(rawBytes).digest('hex'),
  tutorial_source: 'demo-tutorial.json',
  tutorial_sha256: createHash('sha256')
    .update(await readFile(new URL('docs/media/demo-tutorial.json', mediaRoot)))
    .digest('hex'),
  live_queries_added: 0,
  playback_speed: 1,
  media,
}
await writeFile(
  new URL('docs/media/demo-tutorial-render.json', mediaRoot),
  JSON.stringify(report, null, 2) + '\n',
)
console.log(JSON.stringify(report, null, 2))
