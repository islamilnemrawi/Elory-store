const assert = require("node:assert/strict");
const { chromium } = require("playwright");

const BASE_URL = process.env.CATEGORY_MOTION_URL || "http://127.0.0.1:4173/index.html";

function percentile(values, fraction) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * fraction))];
}

async function testViewport(browser, viewport) {
  const page = await browser.newPage({
    viewport: viewport.size,
    deviceScaleFactor: 1,
    isMobile: viewport.mobile,
    hasTouch: viewport.mobile,
    reducedMotion: "no-preference"
  });
  const pageErrors = [];
  page.on("pageerror", error => pageErrors.push(error.message));

  try {
    const response = await page.goto(BASE_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
    assert.ok(response && response.status() < 400, viewport.name + ": storefront must load successfully");
    await page.waitForFunction(() => {
      const track = document.getElementById("categories");
      return !!track && !!track.querySelector("#categorySet .category-card[data-category]") &&
        track.getAnimations().some(animation => animation.animationName === "eloryCategoryInfinite");
    }, { timeout: 45000 });
    await page.waitForTimeout(1200);

    const motion = await page.evaluate(async () => {
      const wrapper = document.getElementById("categoryWrapper");
      const track = document.getElementById("categories");
      const original = track.querySelector("#categorySet");
      const animation = track.getAnimations().find(item => item.animationName === "eloryCategoryInfinite");
      const cloneImages = [...track.querySelectorAll('[data-category-clone="true"] img')];
      const cloneImageModes = cloneImages.map(img => ({
        loading: img.loading,
        decoding: img.decoding,
        fetchPriority: img.getAttribute("fetchpriority")
      }));
      const distance = Number.parseFloat(getComputedStyle(track).getPropertyValue("--elory-category-distance"));
      const duration = Number(animation?.effect?.getTiming?.().duration || 0);
      const samples = [];
      let last = 0;
      const started = performance.now();
      await new Promise(resolve => {
        function frame(now) {
          const transform = getComputedStyle(track).transform;
          const matrix = new DOMMatrixReadOnly(transform === "none" ? undefined : transform);
          if (last) samples.push({ t: now - started, x: matrix.m41, gap: now - last });
          last = now;
          if (now - started < 2200) requestAnimationFrame(frame);
          else resolve();
        }
        requestAnimationFrame(frame);
      });
      const deltas = [];
      for (let i = 1; i < samples.length; i++) {
        const dx = samples[i].x - samples[i - 1].x;
        // Ignore the mathematically expected wrap from the end of a cycle to its start.
        if (Math.abs(dx) < distance * 0.5) deltas.push(dx);
      }
      return {
        wrapperWidth: wrapper.getBoundingClientRect().width,
        originalWidth: original.getBoundingClientRect().width,
        distance,
        duration,
        cloneCount: track.querySelectorAll('[data-category-clone="true"]').length,
        cloneImageCount: cloneImages.length,
        cloneImageModes,
        sampleCount: samples.length,
        frameGapP95: [...samples.map(s => s.gap)].sort((a,b)=>a-b)[Math.floor(Math.max(0,samples.length-1)*0.95)] || 0,
        frameGapMax: Math.max(0, ...samples.map(s => s.gap)),
        negativeMotionRatio: deltas.length ? deltas.filter(dx => dx < 0).length / deltas.length : 0,
        medianStep: deltas.length ? [...deltas].sort((a,b)=>a-b)[Math.floor(deltas.length/2)] : 0,
        maxStep: deltas.length ? Math.max(...deltas.map(Math.abs)) : 0
      };
    });

    console.log(viewport.name + " CATEGORY_MOTION " + JSON.stringify(motion));
    assert.ok(motion.wrapperWidth > 0 && motion.originalWidth > 0, viewport.name + ": category rail must have measurable dimensions");
    assert.ok(motion.distance > 0 && motion.duration >= 1000, viewport.name + ": infinite animation must have a valid distance and duration");
    assert.ok(motion.cloneCount >= 2, viewport.name + ": seamless loop must retain enough repeated sets");
    assert.ok(motion.cloneImageCount === 0 || motion.cloneImageModes.every(img =>
      img.loading === "eager" && img.decoding === "async" && img.fetchPriority === "low"),
      viewport.name + ": visual clones must not lazy-load/decode while entering the viewport");
    assert.ok(motion.sampleCount >= 80, viewport.name + ": animation must be sampled across enough rendered frames");
    assert.ok(motion.negativeMotionRatio >= 0.9, viewport.name + ": automatic motion must remain continuously directed");
    assert.ok(motion.frameGapP95 <= 50, viewport.name + ": 95th-percentile frame gap must stay within 50ms");
    assert.ok(motion.frameGapMax <= 150, viewport.name + ": no rendered-frame gap may exceed 150ms");
    assert.ok(motion.maxStep < 18, viewport.name + ": rail must not jump by a large distance between adjacent frames");
    assert.deepEqual(pageErrors, [], viewport.name + ": page must not emit JavaScript runtime errors");
  } finally {
    await page.close();
  }
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage"] });
  try {
    await testViewport(browser, { name: "mobile-390", size: { width: 390, height: 844 }, mobile: true });
    await testViewport(browser, { name: "desktop-1365", size: { width: 1365, height: 900 }, mobile: false });
    console.log("CATEGORY_MOTION_REGRESSION_PASSED");
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
