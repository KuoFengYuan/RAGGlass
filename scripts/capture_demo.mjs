/** Fresh current-UI footage; all answers come from the real configured model. */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { exportDemoMedia } from "./demo_media.mjs";
import {
  publicWorkspace,
  root,
  fixturePath,
  retrievalFixturePath,
  sampleQuestion,
  unknownQuestion,
  identifierQuestion,
  retentionQuestion,
} from "./public_fixture.mjs";

process.env.PLAYWRIGHT_BROWSERS_PATH ??= fileURLToPath(
  new URL(".cache/playwright", root),
);
const { chromium, expect } = createRequire(
  new URL("frontend/package.json", root),
)("@playwright/test");
const baseURL = process.env.RAGGLASS_BASE_URL || "http://127.0.0.1:8000";
if (process.env.RAGGLASS_DEMO_CLEANUP !== "1")
  throw new Error(
    "Use an empty disposable workspace with RAGGLASS_DEMO_CLEANUP=1; this recording deletes its public PDF/history.",
  );
execFileSync("ffmpeg", ["-version"], { stdio: "ignore" });
const preflight = await publicWorkspace(baseURL, {
  currentDemo: true,
  allowEmpty: true,
});
for (const path of ["/api/documents", "/api/runs"])
  if ((await (await fetch(new URL(path, baseURL))).json()).length)
    throw new Error(
      "Fresh recording requires empty storage; no existing index is reused.",
    );
const output = fileURLToPath(new URL(".data/launch/", root));
const images = fileURLToPath(new URL("docs/images/", root));
await mkdir(`${output}/frames`, { recursive: true });
const tutorial = JSON.parse(
  await readFile(new URL("docs/media/demo-tutorial.json", root), "utf8"),
);
const browser = await chromium.launch({
  channel: process.env.RAGGLASS_BROWSER === "chromium" ? undefined : "chrome",
});
const context = await browser.newContext({
  baseURL,
  viewport: { width: 1440, height: 900 },
  permissions: ["clipboard-read", "clipboard-write"],
  recordVideo: { dir: `${output}/raw`, size: { width: 1440, height: 900 } },
});
const clock = performance.now(),
  page = await context.newPage(),
  video = page.video();
page.setDefaultTimeout(30_000);
const errors = [],
  scenes = [],
  runs = [],
  uploads = [],
  artifacts = [];
page.on("pageerror", (error) => errors.push(error.message));
let start, duration;
const hold = (seconds = 5) => page.waitForTimeout(seconds * 1000);
function scene(id) {
  const content = tutorial.scenes[id];
  if (!content) throw new Error(`Missing scene ${id}`);
  scenes.push({
    id,
    start_seconds: (performance.now() - start) / 1000,
    en: content.en.title,
    "zh-TW": content["zh-TW"].title,
  });
  console.log(`Recording: ${id}`);
}
const frame = (id) => page.screenshot({ path: `${output}/frames/${id}.png` });
async function detail(id) {
  const response = await page.request.get(`/api/runs/${id}`);
  if (!response.ok()) throw new Error(`Run detail HTTP ${response.status()}`);
  return response.json();
}
async function waitRun(id) {
  const deadline = performance.now() + 180_000;
  while (performance.now() < deadline) {
    const run = await detail(id);
    if (run.status !== "running") return run;
    await hold(0.05);
  }
  throw new Error("Live run exceeded 180 seconds");
}
function retain(run) {
  if (
    !run.documents.length ||
    run.documents.some((d) => preflight.fixtures[d.filename] !== d.hash)
  )
    throw new Error("Unexpected run source");
  const ids = new Set(
    run.context?.selected_ids ?? run.evidence.map((e) => e.id),
  );
  if (
    run.citations.some(
      (c) =>
        !ids.has(c.id) ||
        !Object.values(preflight.fixtures).includes(c.document_hash),
    )
  )
    throw new Error("Citation outside the current public context");
  runs.push(run);
}
async function begin(question, kind = "query") {
  if (kind === "query")
    await page.getByLabel("Question", { exact: true }).fill(question);
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().endsWith(`/api/${kind}/start`) && r.status() === 202,
    ),
    page
      .getByRole("button", {
        name:
          kind === "summary"
            ? "Summarize document in 3 points"
            : "Retrieve & answer",
        exact: kind === "summary",
      })
      .click(),
  ]);
  return response.json();
}
async function ask(question, kind = "query") {
  const run = await waitRun((await begin(question, kind)).id);
  retain(run);
  if (run.status !== "completed")
    throw new Error(`Live ${kind} failed: ${run.error_code || run.status}`);
  await expect(
    page.getByRole("button", {
      name:
        kind === "summary"
          ? "Summarize document in 3 points"
          : "Retrieve & answer",
    }),
  ).toBeEnabled();
  await expect(page.getByTestId("answer")).toBeVisible();
  return run;
}
async function upload(path) {
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/documents") && r.request().method() === "POST",
  );
  await page.locator("input[type=file]").setInputFiles(path);
  const accepted = await (await response).json();
  if (
    accepted.duplicate ||
    preflight.fixtures[accepted.filename] !== accepted.hash
  )
    throw new Error("Recording must ingest a fresh known public PDF");
  await expect(page.getByLabel("Active document")).toHaveValue(accepted.id);
  // A previous document's Indexed badge can survive the first upload render.
  // Wait for this document's persisted completion before retaining its receipt.
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`/api/documents/${accepted.id}`)).json())
          .status,
      { timeout: 180_000 },
    )
    .toBe("ready");
  await expect(page.locator(".document-bar .badge")).toHaveText("Indexed", {
    timeout: 180_000,
  });
  const doc = await (
    await page.request.get(`/api/documents/${accepted.id}`)
  ).json();
  uploads.push(doc);
  await expect(page.locator(".pdf-loading")).not.toBeVisible();
  return doc;
}
async function source(number) {
  await page
    .locator(".citation-button")
    .filter({ hasText: `p. ${number}` })
    .first()
    .click();
  await expect(page.getByTestId("pdf-viewer")).toHaveAttribute(
    "data-page",
    String(number),
  );
  await expect(page.locator(".pdf-loading")).not.toBeVisible();
}
async function retrievalOptions(open) {
  const panel = page.locator(".retrieval-options");
  if ((await panel.evaluate((element) => element.open)) !== open)
    await panel.locator("summary").click();
}
try {
  await page.goto(baseURL);
  await page.getByLabel("Language").selectOption("en");
  await expect(
    page.getByRole("heading", { name: "Document workbench", exact: true }),
  ).toBeVisible();
  start = performance.now();
  scene("intro");
  await hold(4);
  scene("upload");
  const guide = await upload(fixturePath);
  await frame("upload");
  await hold(4);
  scene("generation");
  await page.getByTestId("generation-controls").locator("summary").click();
  await page.getByLabel("Temperature", { exact: true }).fill("0.2");
  await page.getByLabel("Top P", { exact: true }).fill("0.9");
  await page.getByLabel("Output token limit", { exact: true }).fill("512");
  await frame("generation");
  await hold(6);
  scene("query");
  const dense = await ask(sampleQuestion);
  if (
    !dense.answerable ||
    dense.settings.retrieval.mode !== "dense" ||
    dense.settings.llm.temperature !== 0.2 ||
    dense.settings.llm.top_p !== 0.9 ||
    dense.settings.llm.max_tokens !== 512
  )
    throw new Error(
      "Dense query/generation settings differ from recorded controls",
    );
  await expect(page.getByTestId("answer")).toContainText("30 MB");
  await page.getByTestId("generation-controls").locator("summary").click();
  await frame("query");
  await hold(5);
  scene("citation");
  await source(2);
  await expect(page.locator(".evidence-box").first()).toBeVisible();
  await page.screenshot({ path: `${images}/demo-poster.png` });
  await frame("citation");
  await hold(6);
  scene("reading");
  await page.getByLabel("Search PDF text", { exact: true }).fill("30 MB");
  await expect(page.locator(".pdf-search-hit.active").first()).toContainText(
    "30",
  );
  await page.getByLabel("PDF zoom", { exact: true }).selectOption("1.25");
  await frame("reading");
  await hold(6);
  await page.getByLabel("PDF zoom", { exact: true }).selectOption("fit");
  await page.getByLabel("Search PDF text", { exact: true }).fill("");
  scene("parsing");
  await page.getByRole("tab", { name: "Parsed content", exact: true }).click();
  await page
    .locator(".parsed-chunk")
    .filter({ hasText: "30 MB" })
    .first()
    .scrollIntoViewIfNeeded();
  await frame("parsing");
  await hold(5);
  await page.getByRole("tab", { name: "Original PDF", exact: true }).click();
  scene("keyword");
  const lab = await upload(retrievalFixturePath);
  await page.locator(".retrieval-options > summary").click();
  await page
    .getByLabel("Retrieval mode", { exact: true })
    .selectOption("keyword");
  await expect(
    page.getByLabel("Minimum score", { exact: true }),
  ).toBeDisabled();
  await page.getByTestId("generation-controls").locator("summary").click();
  await page
    .getByRole("button", { name: "Precise phrasing", exact: true })
    .click();
  await page.getByLabel("Output token limit", { exact: true }).fill("768");
  await page.getByTestId("generation-controls").locator("summary").click();
  const lexical = await ask(retentionQuestion);
  if (
    !lexical.answerable ||
    lexical.settings.retrieval.mode !== "keyword" ||
    "embedding" in lexical.timings_ms
  )
    throw new Error("Chinese BM25 query did not skip query embedding");
  await expect(page.getByTestId("answer")).toContainText(/90|九十/);
  await frame("keyword");
  await hold(6);
  scene("chinese_pdf");
  await source(6);
  await expect(page.locator(".pdf-text-layer")).toContainText("九十天");
  await page.getByLabel("Search PDF text", { exact: true }).fill("九十天");
  await expect(page.locator(".pdf-search-hit.active").first()).toHaveText(
    "九十天",
  );
  await frame("chinese_pdf");
  await hold(6);
  await page.getByLabel("Search PDF text", { exact: true }).fill("");
  scene("hybrid");
  await page
    .getByLabel("Retrieval mode", { exact: true })
    .selectOption("hybrid");
  await page.getByLabel("Top K", { exact: true }).fill("3");
  await page.getByLabel("Candidates per method", { exact: true }).fill("20");
  const hybrid = await ask(identifierQuestion);
  if (
    !hybrid.answerable ||
    hybrid.settings.retrieval.mode !== "hybrid" ||
    !hybrid.retrieval_trace.complete ||
    !hybrid.retrieval_trace.dense.length ||
    !hybrid.retrieval_trace.keyword.length
  )
    throw new Error("Live hybrid query did not preserve both branches");
  await expect(page.getByTestId("answer")).toContainText(/checksum/i);
  await source(1);
  await frame("hybrid");
  await hold(6);
  scene("rankings");
  await retrievalOptions(false);
  await page.getByTestId("retrieval-trace").locator("summary").click();
  await page.getByTestId("retrieval-trace").scrollIntoViewIfNeeded();
  await expect(page.getByTestId("retrieval-trace")).toContainText(
    "Equal RRF scores",
  );
  await page
    .getByTestId("retrieval-trace")
    .locator(".ranking-branch")
    .first()
    .locator("h4")
    .scrollIntoViewIfNeeded();
  await frame("rankings");
  await hold(4);
  await page
    .getByTestId("retrieval-trace")
    .locator(".ranking-branch")
    .nth(1)
    .locator("h4")
    .scrollIntoViewIfNeeded();
  await frame("rankings-keyword");
  await hold(4);
  await page.getByTestId("retrieval-trace").locator("summary").click();
  scene("context");
  await page.getByTestId("workflow-trace").scrollIntoViewIfNeeded();
  if (
    !hybrid.usage?.reported_input_tokens ||
    !hybrid.usage?.reported_output_tokens
  )
    throw new Error("Live model token usage missing");
  await frame("context");
  await hold(7);
  scene("export");
  await page
    .getByRole("button", { name: "Copy answer & sources", exact: false })
    .click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  if (
    !copied.includes(hybrid.answer) ||
    !copied.includes("ragglass-retrieval-lab.pdf")
  )
    throw new Error("Actual clipboard lacked the public answer sources");
  const downloaded = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download Markdown", exact: false })
    .click();
  await (await downloaded).saveAs(`${output}/hybrid-report.md`);
  const markdown = await readFile(`${output}/hybrid-report.md`, "utf8");
  if (
    !markdown.includes("hybrid-rrf") ||
    !markdown.includes("keyword #") ||
    !markdown.includes("dense #")
  )
    throw new Error("Actual Markdown lacked hybrid diagnostics");
  artifacts.push({
    filename: "hybrid-report.md",
    sha256: createHash("sha256").update(markdown).digest("hex"),
  });
  await frame("export");
  await hold(5);
  scene("summary");
  await page.getByLabel("Active document").selectOption(guide.id);
  await page.getByLabel("Question", { exact: true }).fill("");
  const summary = await ask("", "summary");
  if (
    !summary.answerable ||
    !summary.workflow?.nodes.some((n) => n.phase === "map") ||
    !summary.workflow.nodes.some((n) => n.phase === "final") ||
    summary.summary_points?.length !== 3
  )
    throw new Error(
      "Real document summary did not produce three sourced points",
    );
  await page.getByTestId("answer").scrollIntoViewIfNeeded();
  await frame("summary");
  await hold(4);
  await page
    .getByTestId("answer")
    .locator(".citations")
    .scrollIntoViewIfNeeded();
  await frame("summary-bottom");
  await hold(4);
  scene("summary_trace");
  await page
    .getByTestId("workflow-trace")
    .getByRole("heading", { name: "Document summary steps", exact: true })
    .scrollIntoViewIfNeeded();
  await page.locator(".summary-node").first().locator("summary").click();
  await frame("summary_trace");
  await hold(6);
  await page.locator(".summary-node").first().locator("summary").click();
  scene("cancel");
  const pending = await begin("", "summary");
  const deadline = performance.now() + 30_000;
  let generating = false;
  while (performance.now() < deadline) {
    const run = await detail(pending.id);
    if (run.status !== "running")
      throw new Error("Summary finished before the stop demonstration");
    if (run.stage === "generation") {
      generating = true;
      break;
    }
    await hold(0.02);
  }
  if (!generating) throw new Error("Generation was not observed before stop");
  await page.getByRole("button", { name: "Stop query", exact: false }).click();
  const cancelled = await waitRun(pending.id);
  retain(cancelled);
  if (
    cancelled.status !== "cancelled" ||
    !cancelled.evidence.length ||
    cancelled.answer ||
    cancelled.citations.length
  )
    throw new Error("Stop did not retain evidence without an answer");
  await expect(page.locator(".missing-source").first()).toContainText(
    "Query stopped",
  );
  await frame("cancel");
  await hold(6);
  scene("refusal");
  await retrievalOptions(true);
  await page
    .getByLabel("Retrieval mode", { exact: true })
    .selectOption("dense");
  const refused = await ask(unknownQuestion);
  await retrievalOptions(false);
  if (refused.answerable || refused.citations.length)
    throw new Error("Unsupported question was not refused");
  await page.getByTestId("answer").scrollIntoViewIfNeeded();
  await frame("refusal");
  await hold(6);
  scene("history");
  await page.getByTestId("open-history").click();
  await expect(
    page.getByRole("dialog", { name: "Run history", exact: true }),
  ).toBeVisible();
  await hold(3);
  await page
    .locator(".history-item")
    .filter({ hasText: identifierQuestion })
    .first()
    .click();
  await expect(page.getByLabel("Active document")).toHaveValue(lab.id);
  await expect(page.getByLabel("Retrieval mode", { exact: true })).toHaveValue(
    "hybrid",
  );
  await expect(
    page.getByLabel("Candidates per method", { exact: true }),
  ).toHaveValue("20");
  await source(1);
  await retrievalOptions(true);
  await frame("history");
  await hold(5);
  scene("language");
  await page.getByLabel("Language").selectOption("zh-TW");
  await expect(
    page.getByRole("heading", { name: "文件診斷工作台", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Language")).toHaveValue("zh-TW");
  await frame("language");
  await hold(5);
  await page.getByLabel("Language").selectOption("en");
  await page.getByTestId("open-history").click();
  await page
    .locator(".history-item")
    .filter({ hasText: identifierQuestion })
    .first()
    .click();
  await publicWorkspace(baseURL, { currentDemo: true });
  scene("document_cleanup");
  await page.getByTestId("open-library").click();
  const library = page.getByRole("dialog", {
    name: "Document library",
    exact: true,
  });
  await library.getByLabel("Search filenames").fill("ragglass-retrieval-lab");
  await library
    .getByLabel("Select ragglass-retrieval-lab.pdf", { exact: true })
    .check();
  await hold(3);
  await library.getByTestId("delete-selected").click();
  await expect(
    page.getByRole("dialog", { name: "Confirm cleanup", exact: true }),
  ).toContainText("Saved run history remains");
  await hold(3);
  await page.getByTestId("confirm-cleanup").click();
  await expect(library.locator(".document-item")).toHaveCount(0);
  await library.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page.locator(".citation-button").first()).toBeDisabled();
  await page.getByTestId("answer").scrollIntoViewIfNeeded();
  await frame("document_cleanup");
  await hold(5);
  scene("history_cleanup");
  await page.getByTestId("open-history").click();
  const history = page.getByRole("dialog", {
    name: "Run history",
    exact: true,
  });
  await expect(
    history.locator(".history-item").filter({ hasText: identifierQuestion }),
  ).toContainText("Original PDF deleted");
  await history.getByTestId("clear-all").click();
  await expect(
    page.getByRole("dialog", { name: "Confirm cleanup", exact: true }),
  ).toContainText("PDFs and their indexes remain");
  await hold(3);
  await page.getByTestId("confirm-cleanup").click();
  await expect(history.locator(".history-item")).toHaveCount(0);
  await history.getByRole("button", { name: "Close", exact: true }).click();
  if ((await (await page.request.get("/api/documents")).json()).length !== 1)
    throw new Error("History cleanup removed the remaining public PDF");
  await frame("history_cleanup");
  await hold(5);
  scene("closing");
  await hold(6);
  duration = (performance.now() - start) / 1000;
  if (errors.length) throw new Error(errors.join("\n"));
  if (duration > 360)
    throw new Error(
      "Recording exceeded six minutes; inspect the live run without changing playback speed",
    );
} finally {
  await context.close();
  try {
    await video.saveAs(`${output}/live-recording.webm`);
  } finally {
    await browser.close();
  }
}
const report = {
  recorded_at: new Date().toISOString(),
  source_commit: execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: fileURLToPath(root),
    encoding: "utf8",
  }).trim(),
  capture_sha256: createHash("sha256")
    .update(await readFile(new URL("scripts/capture_demo.mjs", root)))
    .digest("hex"),
  document_hash: preflight.documentHash,
  documents: uploads.map((d) => ({
    filename: d.filename,
    hash: d.hash,
    pages: d.page_count,
    chunks: d.chunk_count,
    parser: d.parser,
    chunking: d.chunking,
    embedding: d.embedding,
    timings_ms: d.timings_ms,
  })),
  upload_reused_index: false,
  mock: false,
  playback_speed: 1,
  trimmed_initial_navigation_seconds: (start - clock) / 1000,
  duration_seconds: duration,
  scenes,
  artifacts,
  runs: runs.map((r) => ({
    id: r.id,
    kind: r.kind,
    status: r.status,
    question: r.question,
    model: r.settings.llm.model,
    settings: r.settings,
    answer: r.answer,
    summary_points: r.summary_points,
    answerable: r.answerable,
    citations: r.citations.map((c) => ({
      id: c.id,
      pages: c.pages,
      document_hash: c.document_hash,
    })),
    timings_ms: r.timings_ms,
    model_metrics: r.model_metrics,
    usage: r.usage,
    context: r.context,
    retrieval_trace: r.retrieval_trace,
    workflow: r.workflow && {
      source_chunk_count: r.workflow.source_chunk_count,
      map_batches: r.workflow.map_batches,
      nodes: r.workflow.nodes.map((n) => ({
        id: n.id,
        phase: n.phase,
        status: n.status,
        source_ids: n.source_ids,
        elapsed_ms: n.elapsed_ms,
      })),
    },
    attempts: r.attempts.map((a) => ({
      node: a.node,
      number: a.number,
      status: a.status,
      reason: a.reason,
      error_code: a.error_code,
    })),
  })),
};
await writeFile(
  `${output}/live-runs.json`,
  JSON.stringify(runs, null, 2) + "\n",
);
report.media = await exportDemoMedia(report, output, images);
report.tutorial_source = "demo-tutorial.json";
await writeFile(
  `${output}/recording.json`,
  JSON.stringify(report, null, 2) + "\n",
);
await writeFile(
  new URL("docs/media/demo-recording.json", root),
  JSON.stringify(report, null, 2) + "\n",
);
console.log(
  `Exported fresh ${scenes.length}-scene bilingual tutorial (${duration.toFixed(2)}s, normal speed).`,
);
