/** Record live PDF RAG interaction, then export captioned videos and a real-time GIF. */
import { mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { exportDemoMedia } from "./demo_media.mjs";
import {
  publicWorkspace,
  root,
  fixturePath,
  sampleQuestion,
  unknownQuestion,
} from "./public_fixture.mjs";

process.env.PLAYWRIGHT_BROWSERS_PATH ??= fileURLToPath(
  new URL(".cache/playwright", root),
);
const require = createRequire(new URL("frontend/package.json", root));
const { chromium, expect } = require("@playwright/test");
const baseURL = process.env.RAGGLASS_BASE_URL || "http://127.0.0.1:8000";
if (process.env.RAGGLASS_DEMO_CLEANUP !== "1")
  throw new Error(
    "This tutorial deletes its public fixture and history. Use a disposable workspace and set RAGGLASS_DEMO_CLEANUP=1.",
  );
execFileSync("ffmpeg", ["-version"], { stdio: "ignore" });
const preflight = await publicWorkspace(baseURL);
const output = fileURLToPath(new URL(".data/launch/", root));
const images = fileURLToPath(new URL("docs/images/", root));
await mkdir(output, { recursive: true });
await mkdir(images, { recursive: true });
const browser = await chromium.launch({
  channel: process.env.RAGGLASS_BROWSER === "chromium" ? undefined : "chrome",
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: `${output}/raw`, size: { width: 1440, height: 900 } },
});
const recordingClock = performance.now();
const page = await context.newPage();
const video = page.video();
page.setDefaultTimeout(180_000);
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const scenes = [];
const runs = [];
let start;
let upload;
let duration;
const hold = (seconds) => page.waitForTimeout(seconds * 1000);
function scene(id, en, zh) {
  const time = (performance.now() - start) / 1000;
  scenes.push({ id, start_seconds: time, en, "zh-TW": zh });
  console.log(`Recording: ${id}`);
}
async function ask(question) {
  await page.getByLabel("Question", { exact: true }).fill(question);
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/api/query") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Retrieve & answer" }).click();
  const run = await (await response).json();
  if (run.status !== "completed")
    throw new Error(`Live model query failed: ${run.error_code || run.status}`);
  for (const citation of run.citations) {
    if (
      !run.evidence.some((e) => e.id === citation.id) ||
      citation.document_hash !== preflight.documentHash
    )
      throw new Error(
        "Citation did not belong to the retrieved public fixture.",
      );
  }
  runs.push(run);
  return run;
}
try {
  await page.goto(baseURL);
  await page.getByLabel("Language").selectOption("en");
  await expect(
    page.getByRole("heading", { name: "Document workbench", exact: true }),
  ).toBeVisible();
  start = performance.now();
  scene(
    "intro",
    "RAGGlass · See inside your RAG. Inspect PDF evidence beside the answer.",
    "RAGGlass · See inside your RAG. 將 PDF 證據與答案並排檢視。",
  );
  await hold(4);

  scene(
    "upload",
    "Upload the CC0 sample PDF. This workspace reuses its existing index.",
    "上傳 CC0 範例 PDF；本次工作區重用已建立的索引。",
  );
  const uploadResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/documents") && r.request().method() === "POST",
  );
  await page.locator("input[type=file]").setInputFiles(fixturePath);
  upload = await (await uploadResponse).json();
  if (upload.hash !== preflight.documentHash)
    throw new Error("Unexpected uploaded PDF.");
  await expect(page.locator(".document-bar .badge")).toHaveText("Indexed", {
    timeout: 180_000,
  });
  await expect(page.locator(".pdf-loading")).not.toBeVisible();
  await hold(5);

  scene(
    "query",
    "Ask a table question. Embeddings, retrieval, and model inference run live.",
    "詢問表格內容；embedding、檢索與模型推論都即時執行。",
  );
  const supported = await ask(sampleQuestion);
  if (
    !supported.answerable ||
    !supported.citations.some((c) => c.pages.includes(2))
  ) {
    throw new Error("Live answer did not cite page 2.");
  }
  await expect(page.getByTestId("answer")).toContainText("30 MB");
  await hold(4);

  scene(
    "citation",
    "Click the source: 30 MB is in the original table on page 2.",
    "點擊引用：30 MB 可在原始 PDF 第 2 頁的表格中確認。",
  );
  await page
    .locator(".citation-button")
    .filter({ hasText: "p. 2" })
    .first()
    .hover();
  await hold(1);
  await page
    .locator(".citation-button")
    .filter({ hasText: "p. 2" })
    .first()
    .click();
  await expect(page.getByTestId("pdf-viewer")).toHaveAttribute(
    "data-page",
    "2",
  );
  await expect(page.locator(".pdf-loading")).not.toBeVisible();
  await expect(page.locator(".evidence-box").first()).toBeVisible();
  await page.screenshot({ path: `${images}/demo-poster.png` });
  await hold(6);

  scene(
    "parsing",
    "Compare the parsed table with its original source. Every chunk keeps page IDs.",
    "對照解析表格與原始文件；每個片段保留來源頁碼與 ID。",
  );
  await page.getByRole("tab", { name: "Parsed content", exact: true }).click();
  await page
    .locator(".parsed-chunk")
    .filter({ hasText: "30 MB" })
    .first()
    .scrollIntoViewIfNeeded();
  await hold(5);
  await page.getByRole("tab", { name: "Original PDF", exact: true }).click();

  scene(
    "settings",
    "Inspect saved prompts, model and retrieval settings, plus measured stage timings.",
    "查看保存的 prompt、模型與檢索設定，以及各階段的實測耗時。",
  );
  await page.locator(".run-details > summary").click();
  await page.locator(".run-details").scrollIntoViewIfNeeded();
  await hold(5);
  await page.locator(".run-details > summary").click();

  scene(
    "refusal",
    "Ask about electricity cost: the sample has no evidence for that answer.",
    "詢問年度電費：範例文件沒有可支持此答案的證據。",
  );
  const unsupported = await ask(unknownQuestion);
  if (unsupported.answerable || unsupported.citations.length) {
    throw new Error(
      "The unanswerable question was not refused without citations.",
    );
  }
  await expect(page.getByTestId("answer")).toContainText("cannot be confirmed");
  await page.getByTestId("answer").scrollIntoViewIfNeeded();
  await hold(5);

  scene(
    "history",
    "Reopen a saved run with its question, answer, evidence, and configuration.",
    "重新開啟歷史紀錄，查看該次問題、答案、證據與設定。",
  );
  await page.getByTestId("open-history").click();
  await expect(page.getByRole("dialog", { name: "Run history" })).toBeVisible();
  await hold(3);
  await page
    .locator(".history-item")
    .filter({ hasText: sampleQuestion })
    .first()
    .click();
  await expect(page.getByTestId("answer")).toContainText("30 MB");
  await page
    .locator(".citation-button")
    .filter({ hasText: "p. 2" })
    .first()
    .click();
  await expect(page.getByTestId("pdf-viewer")).toHaveAttribute(
    "data-page",
    "2",
  );
  await page.getByLabel("Question", { exact: true }).scrollIntoViewIfNeeded();
  await hold(2);

  scene(
    "document_cleanup",
    "Search/select the PDF in Document library; confirm Delete selected.",
    "在文件庫搜尋並勾選 PDF，確認刪除所選文件。",
  );
  await page.getByTestId("open-library").click();
  const library = page.getByRole("dialog", {
    name: "Document library",
    exact: true,
  });
  await library.getByLabel("Search filenames").fill("ragglass-field-guide");
  await library
    .getByLabel("Select ragglass-field-guide.pdf", { exact: true })
    .check();
  await hold(3);
  await library.getByTestId("delete-selected").click();
  await expect(
    page.getByRole("dialog", { name: "Confirm cleanup" }),
  ).toContainText("Saved run history remains");
  await hold(3);
  await page.getByTestId("confirm-cleanup").click();
  await expect(library.locator(".document-item")).toHaveCount(0);
  await library.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.locator(".pdf-paper > canvas")).not.toBeVisible();
  await expect(page.getByTestId("answer")).toContainText("30 MB");
  await expect(page.locator(".citation-button").first()).toBeDisabled();
  await page.getByTestId("answer").scrollIntoViewIfNeeded();
  await hold(4);

  scene(
    "history_cleanup",
    "Clear all run history separately; PDFs and indexes are independent.",
    "獨立清空全部執行紀錄；PDF 與索引是另外的清理範圍。",
  );
  await page.getByTestId("open-history").click();
  const history = page.getByRole("dialog", {
    name: "Run history",
    exact: true,
  });
  await expect(history.locator(".history-item").first()).toContainText(
    "Original PDF deleted",
  );
  await hold(3);
  await history.getByTestId("clear-all").click();
  await expect(
    page.getByRole("dialog", { name: "Confirm cleanup" }),
  ).toContainText("PDFs and their indexes remain");
  await hold(3);
  await page.getByTestId("confirm-cleanup").click();
  await expect(history.locator(".history-item")).toHaveCount(0);
  await history.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.getByTestId("answer")).not.toBeVisible();
  await hold(3);

  scene(
    "closing",
    "Try RAGGlass on GitHub. Share a reproducible issue; star it if it helps your work.",
    "到 GitHub 試用 RAGGlass，回報可重現的問題；有幫助也歡迎 Star。",
  );
  await hold(Math.max(4, 85 - (performance.now() - start) / 1000));
  duration = (performance.now() - start) / 1000;
  if (errors.length) throw new Error(errors.join("\n"));
  if (duration > 95)
    throw new Error(
      `Recording took ${duration.toFixed(2)}s; rerun in a fresh disposable workspace with the model warm to stay under 95s.`,
    );
} finally {
  await context.close();
  try {
    await video.saveAs(`${output}/live-recording.webm`);
  } finally {
    await browser.close();
  }
}
const rawStart = (start - recordingClock) / 1000;
const report = {
  recorded_at: new Date().toISOString(),
  source_commit: execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: fileURLToPath(root),
    encoding: "utf8",
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
};
report.media = await exportDemoMedia(report, output, images);
report.tutorial_source = "demo-tutorial.json";
await writeFile(
  `${output}/recording.json`,
  JSON.stringify(report, null, 2) + "\n",
);
const publicMedia = fileURLToPath(new URL("docs/media/", root));
await mkdir(publicMedia, { recursive: true });
await writeFile(
  `${publicMedia}/demo-recording.json`,
  JSON.stringify(report, null, 2) + "\n",
);
console.log(
  `Exported English and Traditional Chinese captioned videos (${duration.toFixed(2)}s), step-by-step VTT/SRT, and a 10s real-time GIF.`,
);
