const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const BASE_URL = process.env.FIRST_PAINT_URL || "http://127.0.0.1:4173/index.html";
const OUT = path.join(process.cwd(), "reports", "first-paint");
fs.mkdirSync(OUT, { recursive: true });
const checkpoints = [0, 100, 250, 500, 1000, 2500, 5000];
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

async function sample(page, label) {
  return page.evaluate(label => {
    const hero = document.querySelector(".hero");
    const slider = document.getElementById("heroSlider");
    if (!hero || !slider) return { label, heroExists: !!hero, sliderExists: !!slider };
    const hs = getComputedStyle(hero);
    const ss = getComputedStyle(slider);
    const rect = slider.getBoundingClientRect();
    const heroVisible = !hero.hidden && hs.display !== "none" && hs.visibility !== "hidden" &&
      hero.getBoundingClientRect().width > 0 && hero.getBoundingClientRect().height > 0;
    const ready = slider.dataset.heroCmsReady === "true";
    const activeSlide = slider.querySelector(":scope > .hero-slide.active") || slider.querySelector(":scope > .hero-slide");
    const activeImage = activeSlide?.querySelector(".elory-hero-fullbleed-picture img, img.hero-product-image");
    const activeVideo = activeSlide?.querySelector(".elory-hero-fullbleed-video");
    const activeSlideMediaReady = !ready ||
      (!activeImage && !activeVideo) ||
      (!!activeImage && activeImage.complete && activeImage.naturalWidth > 0) ||
      (!!activeVideo && activeVideo.readyState >= 2);
    const visibleSlides = [...slider.querySelectorAll(":scope > .hero-slide")].filter(el => {
      const style = getComputedStyle(el);
      const box = el.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" &&
        Number(style.opacity) > 0.01 && box.width > 0 && box.height > 0;
    }).length;
    return {
      label,
      time: Math.round(performance.now()),
      heroVisible,
      sliderOpacity: Number(ss.opacity),
      sliderVisibility: ss.visibility,
      sliderDisplay: ss.display,
      sliderWidth: Math.round(rect.width),
      sliderHeight: Math.round(rect.height),
      backgroundColor: ss.backgroundColor,
      backgroundImage: ss.backgroundImage,
      ready,
      activeSlideMediaReady,
      visibleSlides,
      totalSlides: slider.querySelectorAll(":scope > .hero-slide").length,
      scrollY: Math.round(scrollY),
      documentHeight: document.documentElement.scrollHeight
    };
  }, label);
}

function assertPainted(state, viewportName) {
  assert.ok(state.sliderWidth > 0, viewportName + " " + state.label + ": hero slider must have width");
  assert.ok(state.sliderHeight >= 250, viewportName + " " + state.label + ": hero must reserve its layout height");
  assert.ok(state.sliderOpacity >= 0.99, viewportName + " " + state.label + ": hero region must not be transparent while CMS loads");
  assert.notEqual(state.sliderVisibility, "hidden", viewportName + " " + state.label + ": hero region must remain visible");
  assert.ok(state.visibleSlides >= 1,
    viewportName + " " + state.label + ": a real fallback or CMS campaign slide must remain visible during loading");
  assert.ok(state.activeSlideMediaReady,
    viewportName + " " + state.label + ": CMS must not replace the fallback before active campaign media is ready");
}

async function runViewport(browser, viewport) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 1,
    isMobile: viewport.isMobile,
    hasTouch: viewport.hasTouch
  });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  const pageErrors = [];
  page.on("pageerror", error => pageErrors.push({ message: error.message, stack: error.stack }));
  await page.addInitScript(() => {
    window.__eloryFirstPaintAudit = { cls: 0, shifts: [] };
    try {
      new PerformanceObserver(list => {
        for (const entry of list.getEntries()) {
          if (!entry.hadRecentInput) {
            window.__eloryFirstPaintAudit.cls += entry.value;
            window.__eloryFirstPaintAudit.shifts.push({
              value: entry.value,
              startTime: entry.startTime,
              sources: (entry.sources || []).map(source => {
                const node = source.node;
                return {
                  node: node?.tagName?.toLowerCase?.() || null,
                  id: node?.id || null,
                  className: typeof node?.className === "string" ? node.className : null,
                  previousRect: source.previousRect ? {
                    x: source.previousRect.x, y: source.previousRect.y,
                    width: source.previousRect.width, height: source.previousRect.height
                  } : null,
                  currentRect: source.currentRect ? {
                    x: source.currentRect.x, y: source.currentRect.y,
                    width: source.currentRect.width, height: source.currentRect.height
                  } : null
                };
              })
            });
          }
        }
      }).observe({ type: "layout-shift", buffered: true });
    } catch (_) {}
  });

  const results = { viewport: viewport.name, samples: [], pageErrors };
  try {
    const response = await page.goto(BASE_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
    results.httpStatus = response ? response.status() : null;
    assert.ok(response && response.status() < 400, viewport.name + ": storefront must return HTTP < 400");

    await page.evaluate(() => {
      history.scrollRestoration = "manual";
      window.scrollTo(0, 0);
    });
    const started = Date.now();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    for (const checkpoint of checkpoints) {
      const remaining = checkpoint - (Date.now() - started);
      if (remaining > 0) await wait(remaining);
      const naturalScrollY = await page.evaluate(() => Math.round(window.scrollY));
      if (naturalScrollY > 5) {
        results.autoScrollEvents = results.autoScrollEvents || [];
        results.autoScrollEvents.push({ checkpoint, scrollY: naturalScrollY });
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
      }
      const state = await sample(page, String(checkpoint) + "ms");
      state.autoScrollY = naturalScrollY;
      results.samples.push(state);
      assertPainted(state, viewport.name);
      await page.screenshot({
        path: path.join(OUT, viewport.name + "-" + String(checkpoint).padStart(4, "0") + "ms.png"),
        fullPage: false,
        animations: "disabled"
      });
    }

    results.final = await page.evaluate(() => ({
      heroReady: document.getElementById("heroSlider")?.dataset.heroCmsReady === "true",
      audit: window.__eloryFirstPaintAudit || { cls: null, shifts: [] }
    }));

    // Exercise a real refresh from a scrolled position and inspect the first rendered frame.
    await page.evaluate(() => {
      history.scrollRestoration = "auto";
      window.scrollTo(0, Math.min(220, document.documentElement.scrollHeight - innerHeight));
    });
    await wait(150);
    await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const reloadState = await sample(page, "reload-first-frame");
    results.reloadFirstFrame = reloadState;
    assertPainted(reloadState, viewport.name);
    await page.screenshot({
      path: path.join(OUT, viewport.name + "-reload-first-frame.png"),
      fullPage: false,
      animations: "disabled"
    });
  } catch (error) {
    results.failure = String(error).slice(0, 1200);
    throw error;
  } finally {
    results.pageErrors = pageErrors;
    await context.close();
    fs.writeFileSync(path.join(OUT, viewport.name + "-report.json"), JSON.stringify(results, null, 2));
  }
  return results;
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage"] });
  const results = [];
  try {
    results.push(await runViewport(browser, {
      name: "mobile-390x844", width: 390, height: 844, isMobile: true, hasTouch: true
    }));
    results.push(await runViewport(browser, {
      name: "desktop-1365x900", width: 1365, height: 900, isMobile: false, hasTouch: false
    }));
  } finally {
    await browser.close();
  }
  const summary = {
    generatedAt: new Date().toISOString(),
    url: BASE_URL,
    runs: results.map(result => ({
      viewport: result.viewport,
      httpStatus: result.httpStatus,
      samples: result.samples.length,
      heroReadyAtEnd: result.final?.heroReady ?? null,
      cls: result.final?.audit?.cls ?? null,
      pageErrors: result.pageErrors?.length ?? 0,
      reloadFirstFrame: result.reloadFirstFrame
    }))
  };
  fs.writeFileSync(path.join(OUT, "summary.json"), JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
