#!/usr/bin/env node

const { createRequire } = require("module");
const fs = require("fs");
const requireFromHere = createRequire(__filename);
const { chromium } = requireFromHere("playwright");

const url = process.argv[2];

if (!url) {
  console.error("Usage: browser_fetch_jd.cjs <url>");
  process.exit(2);
}

async function main() {
  const executablePath = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
  ].find((candidate) => fs.existsSync(candidate));

  const browser = await chromium.launch({
    headless: true,
    ...(executablePath ? { executablePath } : {}),
    args: ["--disable-dev-shm-usage", "--no-sandbox"],
  });

  try {
    const page = await browser.newPage({
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      viewport: { width: 1365, height: 1400 },
    });

    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(5000);

    try {
      await page.waitForLoadState("networkidle", { timeout: 10000 });
    } catch (_) {
      // Many job pages keep analytics/network requests open. Visible text is enough.
    }

    const text = await page.evaluate(() => {
      const selectors = [
        "main",
        "[role='main']",
        "article",
        "[data-automation-id='jobPostingDescription']",
        ".job-description",
        "#job-description",
        "body",
      ];
      const node = selectors.map((selector) => document.querySelector(selector)).find(Boolean);
      return (node ? node.innerText : document.body.innerText) || "";
    });

    console.log(
      JSON.stringify({
        url: page.url(),
        title: await page.title(),
        text,
      })
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
