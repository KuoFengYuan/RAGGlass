/** Verify actual GitHub README video rendering and playback without signing in. */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const root = new URL("../", import.meta.url);
process.env.PLAYWRIGHT_BROWSERS_PATH ??= fileURLToPath(
  new URL(".cache/playwright", root),
);
const require = createRequire(new URL("frontend/package.json", root));
const { chromium, expect } = require("@playwright/test");
const embeds = JSON.parse(
  await readFile(new URL("docs/media/demo-embeds.json", root), "utf8"),
);
const rendering = JSON.parse(
  await readFile(new URL("docs/media/demo-tutorial-render.json", root), "utf8"),
);
const recording = JSON.parse(
  await readFile(new URL("docs/media/demo-recording.json", root), "utf8"),
);
const ref = process.env.RAGGLASS_GITHUB_REF || "main";
const output = fileURLToPath(new URL(".data/launch/", root));
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  channel: process.env.RAGGLASS_BROWSER === "chromium" ? undefined : "chrome",
});
const report = {
  checked_at: new Date().toISOString(),
  ref,
  anonymous: true,
  readmes: [],
};
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1100 },
  });
  for (const [language, filename, heading] of [
    ["en", "README.md", "Watch the demo"],
    ["zh-TW", "README.zh-TW.md", "觀看操作示範"],
  ]) {
    const page = await context.newPage();
    const url = `https://github.com/KuoFengYuan/RAGGlass/blob/${encodeURIComponent(ref)}/${filename}`;
    await page.goto(url, { waitUntil: "domcontentloaded" });
    const article = page.locator("article.markdown-body");
    await expect(
      article.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
    const watch = article.getByRole("link", { name: heading, exact: true });
    const href = await watch.getAttribute("href");
    expect(href).toMatch(/^#(?:user-content-)?/);
    await watch.click();
    expect(decodeURIComponent(new URL(page.url()).hash)).toBe(
      decodeURIComponent(href),
    );
    await expect(
      article.locator('a[href*="/releases/download/"][href*=".mp4"]'),
    ).toHaveCount(0);

    const video = article.locator("video");
    await expect(video).toHaveCount(1);
    await video.scrollIntoViewIfNeeded();
    await video.evaluate((element) => element.play());
    const handle = await video.elementHandle();
    await page.waitForFunction((element) => element.readyState >= 2, handle, {
      timeout: 30_000,
    });
    const attachment = embeds.videos[language];
    const id = new URL(attachment.url).pathname.split("/").at(-1);
    const metadata = await video.evaluate(
      (element, id) => ({
        attachment_matches: new URL(element.currentSrc).pathname.includes(id),
        controls: element.controls,
        duration_seconds: element.duration,
        width: element.videoWidth,
        height: element.videoHeight,
      }),
      id,
    );
    expect(metadata.attachment_matches).toBe(true);
    expect(metadata.controls).toBe(true);
    expect(metadata.width).toBe(rendering.media[language].width);
    expect(metadata.height).toBe(rendering.media[language].height);
    expect(
      Math.abs(
        metadata.duration_seconds - rendering.media[language].duration_seconds,
      ),
    ).toBeLessThan(0.1);
    await expect
      .poll(() => video.evaluate((element) => element.currentTime))
      .toBeGreaterThan(0.5);
    await video.evaluate((element) => {
      element.pause();
      element.currentTime = 25;
    });
    await page.waitForFunction(
      (element) =>
        !element.seeking &&
        element.readyState >= 2 &&
        Math.abs(element.currentTime - 25) < 0.1,
      handle,
    );
    await video.screenshot({ path: `${output}/readme-player-${language}.png` });
    const cleanupSeeks = [];
    for (const sceneId of ["document_cleanup", "history_cleanup"]) {
      const scene = recording.scenes.find((item) => item.id === sceneId);
      if (!scene) continue;
      const seconds = scene.start_seconds + 4.5;
      await video.evaluate((element, seconds) => {
        element.currentTime = seconds;
      }, seconds);
      await page.waitForFunction(
        ({ element, seconds }) =>
          !element.seeking &&
          element.readyState >= 2 &&
          Math.abs(element.currentTime - seconds) < 0.1,
        { element: handle, seconds },
      );
      await video.screenshot({
        path: `${output}/readme-${sceneId}-${language}.png`,
      });
      cleanupSeeks.push({ scene: sceneId, seconds });
    }
    report.readmes.push({
      language,
      url,
      public_video_url: attachment.url,
      ...metadata,
      played: true,
      seek_seconds: 25,
      download_links: 0,
      cleanup_seeks: cleanupSeeks,
    });
    await page.close();
  }
} finally {
  await browser.close();
}
await writeFile(
  `${output}/readme-check.json`,
  JSON.stringify(report, null, 2) + "\n",
);
console.log(JSON.stringify(report, null, 2));
