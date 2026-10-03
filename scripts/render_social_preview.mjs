/** Render bilingual social cards with actual, public-fixture interface captures. */
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const root = new URL('../', import.meta.url)
process.env.PLAYWRIGHT_BROWSERS_PATH ??= fileURLToPath(new URL('.cache/playwright', root))
const require = createRequire(new URL('frontend/package.json', root))
const { chromium } = require('@playwright/test')
const browser = await chromium.launch({
  channel: process.env.RAGGLASS_BROWSER === 'chromium' ? undefined : 'chrome',
})
const page = await browser.newPage({
  viewport: { width: 1280, height: 640 },
  deviceScaleFactor: 1,
})
const output = fileURLToPath(new URL('docs/images/', root))
const reports = []
try {
  for (const language of ['en', 'zh-TW']) {
    const english = language === 'en'
    const suffix = english ? '' : '.zh-TW'
    const source = english ? 'demo-poster.png' : 'workbench.zh-TW.png'
    const screenshot = (await readFile(`${output}/${source}`)).toString('base64')
    const title = english
      ? 'Know where your<br>RAG answer<br>came from.'
      : '看見 RAG 答案<br>背後的文件證據。'
    const description = english
      ? 'Original PDFs, retrieved evidence,<br>and answers, side by side.'
      : '把原始 PDF、檢索片段與答案<br>放在同一個工作台對照。'
    await page.setContent(`<!doctype html><html lang="${language}"><meta charset="utf-8">
      <style>
      * { box-sizing: border-box; } body { margin: 0; background: #f4efe3; color: #242820; font-family: 'Noto Sans Display', 'Noto Sans CJK TC', sans-serif; }
      main { position: relative; width: 1280px; height: 640px; overflow: hidden; }
      header { height: 74px; background: #252920; color: #f7f0e3; display: flex; align-items: center; padding: 0 50px; gap: 18px; }
      header svg { width: 30px; height: 36px; color: #cea484; }
      .brand { font: 34px Georgia, 'Noto Serif', serif; letter-spacing: -1px; } .brand em { font-style: normal; color: #cea484; }
      .motto { margin-left: auto; color: #d5cfbf; font: italic 19px Georgia, serif; }
      .copy { position: absolute; top: 120px; left: 50px; width: 448px; }
      .eyebrow { color: #a44b30; font-size: 12px; letter-spacing: 2px; margin: 0 0 22px; font-weight: 700; }
      h1 { font-family: Georgia, 'Noto Serif CJK TC', serif; font-weight: 500; font-size: ${english ? 51 : 43}px; line-height: ${english ? 1.1 : 1.38}; letter-spacing: ${english ? '-1.7px' : '-1px'}; margin: 0; }
      .description { margin-top: 28px; font-size: 19px; line-height: 1.65; color: #5c6057; }
      .features { position: absolute; left: 50px; top: 508px; font-size: 13px; color: #a44b30; font-weight: 600; }
      .preview { position: absolute; left: 527px; top: 115px; width: 708px; border: 1px solid #c5c0b2; box-shadow: 0 18px 35px #24282020; background: #f9f6ee; }
      .window { height: 25px; display: flex; align-items: center; gap: 6px; padding-left: 11px; border-bottom: 1px solid #c5c0b2; background: #e7e1d4; }
      .window i { display: block; width: 5px; height: 5px; border-radius: 50%; background: #9a978b; }
      .window span { margin-left: 8px; font-size: 10px; color: #5c6057; }
      .preview img { display: block; width: 100%; height: 434px; object-fit: contain; background: #f4efe3; }
      footer { position: absolute; left: 50px; right: 46px; bottom: 24px; border-top: 1px solid #ccc6b8; padding-top: 17px; display: flex; justify-content: space-between; font-size: 13px; }
      footer span { font-size: 10px; color: #73776b; letter-spacing: 1px; }
      </style><main>
      <header><svg viewBox="0 0 36 40" fill="none"><path d="M18 2 34 11v18l-16 9-16-9V11L18 2Z" stroke="currentColor" stroke-width="1.5"/><path d="m2 11 16 9 16-9M18 20v18M10 6.5 26 16v18" stroke="currentColor" stroke-width="1.5"/></svg><div class="brand">RAG<em>Glass</em></div><div class="motto">See inside your RAG.</div></header>
      <div class="copy"><p class="eyebrow">${english ? 'A DOCUMENT RAG WORKBENCH' : '文件 RAG 診斷工作台'}</p><h1>${title}</h1><p class="description">${description}</p></div>
      <div class="features">${english ? 'Local · Open source · Connect your model service' : '地端部署 · 開源 · 連接自己的模型服務'}</div>
      <div class="preview"><div class="window"><i></i><i></i><i></i><span>RAGGlass / ${english ? 'Document workbench' : '文件診斷工作台'}</span></div><img alt="Actual RAGGlass interface" src="data:image/png;base64,${screenshot}"></div>
      <footer>github.com/KuoFengYuan/RAGGlass<span>${english ? 'ACTUAL INTERFACE · CC0 SAMPLE · LIVE MODEL' : '實際介面 · CC0 範例 · 真實模型推論'}</span></footer>
      </main></html>`)
    await page.evaluate(async () => {
      await document.fonts.ready
      await Promise.all([...document.images].map((image) => image.decode()))
    })
    const image = await page.screenshot({
      path: `${output}/social-preview${suffix}.png`,
    })
    if (image.length >= 1_000_000) throw new Error('Social card exceeds the 1 MB upload limit.')
    reports.push({
      language,
      source,
      width: 1280,
      height: 640,
      bytes: image.length,
    })
    console.log(`Rendered ${language} social card: 1280 × 640, ${image.length} bytes`)
  }
} finally {
  await browser.close()
}
const data = fileURLToPath(new URL('.data/launch/', root))
await mkdir(data, { recursive: true })
await writeFile(`${data}/social-cards.json`, JSON.stringify(reports, null, 2) + '\n')
