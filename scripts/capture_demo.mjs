/** Record live PDF RAG interaction, then export captioned videos and a real-time GIF. */
import { mkdir, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  publicWorkspace,
  root,
  fixturePath,
  sampleQuestion,
  unknownQuestion,
} from './public_fixture.mjs'

process.env.PLAYWRIGHT_BROWSERS_PATH ??= fileURLToPath(new URL('.cache/playwright', root))
const require = createRequire(new URL('frontend/package.json', root))
const { chromium, expect } = require('@playwright/test')
const baseURL = process.env.RAGGLASS_BASE_URL || 'http://127.0.0.1:8000'
execFileSync('ffmpeg', ['-version'], { stdio: 'ignore' })
const preflight = await publicWorkspace(baseURL)
const output = fileURLToPath(new URL('.data/launch/', root))
const images = fileURLToPath(new URL('docs/images/', root))
await mkdir(output, { recursive: true })
await mkdir(images, { recursive: true })
const browser = await chromium.launch({
  channel: process.env.RAGGLASS_BROWSER === 'chromium' ? undefined : 'chrome',
})
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: `${output}/raw`, size: { width: 1440, height: 900 } },
})
const recordingClock = performance.now()
const page = await context.newPage()
const video = page.video()
page.setDefaultTimeout(180_000)
const errors = []
page.on('pageerror', (error) => errors.push(error.message))
const scenes = []
const runs = []
let start
let upload
let duration
const hold = (seconds) => page.waitForTimeout(seconds * 1000)
function scene(id, en, zh) {
  const time = (performance.now() - start) / 1000
  scenes.push({ id, start_seconds: time, en, 'zh-TW': zh })
  console.log(`Recording: ${id}`)
}
async function ask(question) {
  await page.getByLabel('Question', { exact: true }).fill(question)
  const response = page.waitForResponse(
    (r) => r.url().endsWith('/api/query') && r.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Retrieve & answer' }).click()
  const run = await (await response).json()
  if (run.status !== 'completed')
    throw new Error(`Live model query failed: ${run.error_code || run.status}`)
  for (const citation of run.citations) {
    if (
      !run.evidence.some((e) => e.id === citation.id) ||
      citation.document_hash !== preflight.documentHash
    )
      throw new Error('Citation did not belong to the retrieved public fixture.')
  }
  runs.push(run)
  return run
}
try {
  await page.goto(baseURL)
  await page.getByLabel('Language').selectOption('en')
  await expect(page.getByRole('heading', { name: 'Document workbench', exact: true })).toBeVisible()
  start = performance.now()
  scene(
    'intro',
    'RAGGlass · See inside your RAG. Inspect PDF evidence beside the answer.',
    'RAGGlass · See inside your RAG. 將 PDF 證據與答案並排檢視。',
  )
  await hold(4)

  scene(
    'upload',
    'Upload the CC0 sample PDF. This workspace reuses its existing index.',
    '上傳 CC0 範例 PDF；本次工作區重用已建立的索引。',
  )
  const uploadResponse = page.waitForResponse(
    (r) => r.url().endsWith('/api/documents') && r.request().method() === 'POST',
  )
  await page.locator('input[type=file]').setInputFiles(fixturePath)
  upload = await (await uploadResponse).json()
  if (upload.hash !== preflight.documentHash) throw new Error('Unexpected uploaded PDF.')
  await expect(page.locator('.document-bar .badge')).toHaveText('Indexed', {
    timeout: 180_000,
  })
  await expect(page.locator('.pdf-loading')).not.toBeVisible()
  await hold(5)

  scene(
    'query',
    'Ask a table question. Embeddings, retrieval, and model inference run live.',
    '詢問表格內容；embedding、檢索與模型推論都即時執行。',
  )
  const supported = await ask(sampleQuestion)
  if (!supported.answerable || !supported.citations.some((c) => c.pages.includes(2))) {
    throw new Error('Live answer did not cite page 2.')
  }
  await expect(page.getByTestId('answer')).toContainText('30 MB')
  await hold(4)

  scene(
    'citation',
    'Click the source: 30 MB is in the original table on page 2.',
    '點擊引用：30 MB 可在原始 PDF 第 2 頁的表格中確認。',
  )
  await page.locator('.citation-button').filter({ hasText: 'p. 2' }).first().hover()
  await hold(1)
  await page.locator('.citation-button').filter({ hasText: 'p. 2' }).first().click()
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '2')
  await expect(page.locator('.pdf-loading')).not.toBeVisible()
  await expect(page.locator('.evidence-box').first()).toBeVisible()
  await page.screenshot({ path: `${images}/demo-poster.png` })
  await hold(6)

  scene(
    'parsing',
    'Compare the parsed table with its original source. Every chunk keeps page IDs.',
    '對照解析表格與原始文件；每個片段保留來源頁碼與 ID。',
  )
  await page.getByRole('tab', { name: 'Parsed content', exact: true }).click()
  await page.locator('.parsed-chunk').filter({ hasText: '30 MB' }).first().scrollIntoViewIfNeeded()
  await hold(5)
  await page.getByRole('tab', { name: 'Original PDF', exact: true }).click()

  scene(
    'settings',
    'Inspect saved prompts, model and retrieval settings, plus measured stage timings.',
    '查看保存的 prompt、模型與檢索設定，以及各階段的實測耗時。',
  )
  await page.locator('.run-details > summary').click()
  await page.locator('.run-details').scrollIntoViewIfNeeded()
  await hold(5)
  await page.locator('.run-details > summary').click()

  scene(
    'refusal',
    'Ask about electricity cost: the sample has no evidence for that answer.',
    '詢問年度電費：範例文件沒有可支持此答案的證據。',
  )
  const unsupported = await ask(unknownQuestion)
  if (unsupported.answerable || unsupported.citations.length) {
    throw new Error('The unanswerable question was not refused without citations.')
  }
  await expect(page.getByTestId('answer')).toContainText('cannot be confirmed')
  await page.getByTestId('answer').scrollIntoViewIfNeeded()
  await hold(5)

  scene(
    'history',
    'Reopen a saved run with its question, answer, evidence, and configuration.',
    '重新開啟歷史紀錄，查看該次問題、答案、證據與設定。',
  )
  await page.getByTestId('open-history').click()
  await expect(page.getByRole('dialog', { name: 'Run history' })).toBeVisible()
  await hold(3)
  await page.locator('.history-item').filter({ hasText: sampleQuestion }).first().click()
  await expect(page.getByTestId('answer')).toContainText('30 MB')
  await page.locator('.citation-button').filter({ hasText: 'p. 2' }).first().click()
  await expect(page.getByTestId('pdf-viewer')).toHaveAttribute('data-page', '2')
  await page.getByLabel('Question', { exact: true }).scrollIntoViewIfNeeded()
  await hold(2)

  scene(
    'closing',
    'Try RAGGlass on GitHub. Share a reproducible issue; star it if it helps your work.',
    '到 GitHub 試用 RAGGlass，回報可重現的問題；有幫助也歡迎 Star。',
  )
  await hold(Math.max(4, 55 - (performance.now() - start) / 1000))
  duration = (performance.now() - start) / 1000
  if (errors.length) throw new Error(errors.join('\n'))
  if (duration > 60)
    throw new Error(
      `Recording took ${duration.toFixed(2)}s; rerun with the model warm to stay under 60s.`,
    )
} finally {
  await context.close()
  try {
    await video.saveAs(`${output}/live-recording.webm`)
  } finally {
    await browser.close()
  }
}
const rawStart = (start - recordingClock) / 1000
const clock = (seconds, separator = '.') => {
  const milliseconds = Math.round(seconds * 1000)
  const h = Math.floor(milliseconds / 3600000)
  const m = Math.floor(milliseconds / 60000) % 60
  const s = Math.floor(milliseconds / 1000) % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}${separator}${String(milliseconds % 1000).padStart(3, '0')}`
}
for (const language of ['en', 'zh-TW']) {
  const suffix = language === 'en' ? '' : '.zh-TW'
  const cues = scenes.map((s, index) => {
    const end = scenes[index + 1]?.start_seconds ?? duration
    return { start: s.start_seconds, end, text: s[language] }
  })
  await writeFile(
    `${output}/ragglass-demo${suffix}.srt`,
    cues
      .map((c, i) => `${i + 1}\n${clock(c.start, ',')} --> ${clock(c.end, ',')}\n${c.text}\n`)
      .join('\n'),
  )
  await writeFile(
    `${output}/ragglass-demo${suffix}.vtt`,
    'WEBVTT\n\n' + cues.map((c) => `${clock(c.start)} --> ${clock(c.end)}\n${c.text}\n`).join('\n'),
  )
  const assTime = (seconds) => clock(seconds).slice(1, -1)
  const subtitle =
    `[Script Info]\nScriptType: v4.00+\nPlayResX: 1440\nPlayResY: 1000\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Noto Sans CJK TC,28,&H00F5EEE6,&H00F5EEE6,&H00232823,&H00232823,0,0,0,0,100,100,0,0,1,0,0,2,50,50,25,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n` +
    cues
      .map((c) => `Dialogue: 0,${assTime(c.start)},${assTime(c.end)},Default,,0,0,0,,${c.text}`)
      .join('\n')
  await writeFile(`${output}/captions${suffix}.ass`, subtitle)
  execFileSync(
    'ffmpeg',
    [
      '-y',
      '-hide_banner',
      '-loglevel',
      'error',
      '-ss',
      rawStart.toFixed(3),
      '-i',
      'live-recording.webm',
      '-t',
      duration.toFixed(3),
      '-vf',
      `pad=iw:ih+100:0:0:color=0x232823,ass=captions${suffix}.ass`,
      '-c:v',
      'libx264',
      '-preset',
      'fast',
      '-crf',
      '23',
      '-pix_fmt',
      'yuv420p',
      '-r',
      '24',
      '-an',
      '-movflags',
      '+faststart',
      '-threads',
      '4',
      `ragglass-demo${suffix}.mp4`,
    ],
    { cwd: output, stdio: 'inherit' },
  )
}
const clipStart = Math.max(0, scenes.find((s) => s.id === 'citation').start_seconds - 1)
for (const suffix of ['', '.zh-TW']) {
  execFileSync(
    'ffmpeg',
    [
      '-y',
      '-hide_banner',
      '-loglevel',
      'error',
      '-ss',
      clipStart.toFixed(3),
      '-i',
      `ragglass-demo${suffix}.mp4`,
      '-t',
      '10',
      '-filter_complex',
      '[0:v]fps=8,scale=864:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=3',
      '-loop',
      '0',
      `${images}/demo${suffix}.gif`,
    ],
    { cwd: output, stdio: 'inherit' },
  )
}
const report = {
  recorded_at: new Date().toISOString(),
  source_commit: execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: fileURLToPath(root),
    encoding: 'utf8',
  }).trim(),
  document_hash: preflight.documentHash,
  upload_reused_index: Boolean(upload.duplicate),
  mock: false,
  playback_speed: 1,
  trimmed_initial_navigation_seconds: rawStart,
  duration_seconds: duration,
  scenes,
  runs: runs.map((r) => ({
    id: r.id,
    question: r.question,
    model: r.settings.llm.model,
    answer: r.answer,
    answerable: r.answerable,
    citations: r.citations.map((c) => ({ id: c.id, pages: c.pages })),
    timings_ms: r.timings_ms,
    model_metrics: r.model_metrics,
  })),
}
report.media = Object.fromEntries(
  ['en', 'zh-TW'].map((language) => {
    const suffix = language === 'en' ? '' : '.zh-TW'
    const info = JSON.parse(
      execFileSync(
        'ffprobe',
        [
          '-v',
          'error',
          '-show_entries',
          'format=duration:stream=codec_name,width,height,pix_fmt',
          '-of',
          'json',
          `ragglass-demo${suffix}.mp4`,
        ],
        { cwd: output, encoding: 'utf8' },
      ),
    )
    return [
      language,
      {
        filename: `ragglass-demo${suffix}.mp4`,
        duration_seconds: Number(info.format.duration),
        ...info.streams[0],
      },
    ]
  }),
)
await writeFile(`${output}/recording.json`, JSON.stringify(report, null, 2) + '\n')
const publicMedia = fileURLToPath(new URL('docs/media/', root))
await mkdir(publicMedia, { recursive: true })
await writeFile(`${publicMedia}/demo-recording.json`, JSON.stringify(report, null, 2) + '\n')
console.log(
  `Exported English and Traditional Chinese captioned videos (${duration.toFixed(2)}s), VTT/SRT, and a 10s real-time GIF.`,
)
