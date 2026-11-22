const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

(async () => {
  const reportDir = path.join(process.cwd(), "reports");
  fs.mkdirSync(reportDir, { recursive: true });
  const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage"] });
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    isMobile: true,
    hasTouch: true
  });
  page.setDefaultTimeout(20000);
  const pageErrors = [];
  page.on("pageerror", error => pageErrors.push(String(error)));

  try {
    await page.goto("http://127.0.0.1:4173/index.html", { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.locator("#eloryGlobalStickyShell").waitFor();
    await page.waitForTimeout(2500);
    await page.evaluate(async () => {
      document.documentElement.style.scrollBehavior = "auto";
      document.body.style.scrollBehavior = "auto";
      history.scrollRestoration = "manual";
      history.replaceState(history.state, "", location.pathname + location.search);
      window.scrollTo({ top: 0, left: 0, behavior: "instant" });
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });

    const start = await page.evaluate(() => {
      document.documentElement.style.scrollBehavior = "auto";
      const shell = document.getElementById("eloryGlobalStickyShell");
      const fullNav = shell.querySelector(":scope > .elory-reference-nav");
      const fullNavBox = fullNav.getBoundingClientRect();
      return {
        viewport: { width: innerWidth, height: innerHeight },
        scrollY: window.scrollY,
        bodyScrollTop: document.body.scrollTop,
        rootScrollTop: document.documentElement.scrollTop,
        shellHeight: shell.getBoundingClientRect().height,
        fullNavSize: { width: fullNavBox.width, height: fullNavBox.height },
        documentHeight: document.documentElement.scrollHeight,
        compact: shell.classList.contains("elory-notch-compact"),
        shellPosition: getComputedStyle(shell).position,
        headerVisibility: getComputedStyle(shell.querySelector(".header")).visibility,
        navCount: shell.querySelectorAll(":scope > .elory-reference-nav").length,
        maxScroll: Math.max(0, document.documentElement.scrollHeight - innerHeight)
      };
    });
    console.log("START_STATE " + JSON.stringify(start));
    assert.deepEqual(start.viewport, { width: 390, height: 844 }, "must run at a real 390x844 CSS viewport");
    assert.equal(start.scrollY, 0, "regression test must begin at page top");
    assert.equal(start.compact, false, "page must start in full-header state");
    assert.equal(start.shellPosition, "relative", "the full header shell must not be a large sticky repaint layer");
    assert.ok(start.maxScroll > 300, "page needs enough scroll range for the regression test");
    await page.evaluate(size => { window.__eloryStartNavSize = size; }, start.fullNavSize);

    await page.evaluate(() => {
      const shell = document.getElementById("eloryGlobalStickyShell");
      const audit = window.__eloryNotchAudit = { toggles: [], samples: [], frameGaps: [], cls: 0, layoutShifts: [] };
      let lastCompact = shell.classList.contains("elory-notch-compact");
      new MutationObserver(() => {
        const compact = shell.classList.contains("elory-notch-compact");
        if (compact !== lastCompact) {
          audit.toggles.push({
            compact,
            scrollY,
            shellHeight: shell.getBoundingClientRect().height,
            documentHeight: document.documentElement.scrollHeight,
            time: performance.now()
          });
          lastCompact = compact;
        }
      }).observe(shell, { attributes: true, attributeFilter: ["class"] });
      if ("PerformanceObserver" in window) {
        try {
          new PerformanceObserver(list => {
            for (const entry of list.getEntries()) {
              if (!entry.hadRecentInput) {
                audit.cls += entry.value;
                const sources = Array.from(entry.sources || []).map(source => {
                  const node = source.node;
                  const name = node ? node.tagName.toLowerCase() +
                    (node.id ? "#" + node.id : "") +
                    (typeof node.className === "string" && node.className.trim() ? "." + node.className.trim().split(/\s+/).join(".") : "") : "unknown";
                  return { node: name, previousRect: source.previousRect, currentRect: source.currentRect };
                });
                audit.layoutShifts.push({ value: entry.value, startTime: entry.startTime, sources });
              }
            }
          }).observe({ type: "layout-shift", buffered: true });
        } catch (_) {}
      }
    });

    const target = Math.min(520, start.maxScroll - 20);
    async function slowScroll(to) {
      await page.evaluate(async targetY => {
        const audit = window.__eloryNotchAudit;
        let y = Math.round(scrollY);
        const direction = targetY >= y ? 1 : -1;
        let previousFrame = performance.now();
        while ((direction > 0 && y < targetY) || (direction < 0 && y > targetY)) {
          y += direction;
          window.scrollTo(0, y);
          const frameTime = await new Promise(resolve => requestAnimationFrame(resolve));
          const gap = frameTime - previousFrame;
          if (gap > 34) audit.frameGaps.push(gap);
          previousFrame = frameTime;
          if (y <= 5 || Math.abs(y - 48) <= 2 || Math.abs(y - 88) <= 2 || y % 80 === 0) {
            const shell = document.getElementById("eloryGlobalStickyShell");
            audit.samples.push({
              requestedY: y,
              actualY: Math.round(scrollY),
              shellHeight: shell.getBoundingClientRect().height,
              documentHeight: document.documentElement.scrollHeight,
              compact: shell.classList.contains("elory-notch-compact")
            });
          }
        }
      }, to);
    }

    await slowScroll(target);
    await slowScroll(0);
    await slowScroll(target);
    await slowScroll(0);
    await page.waitForTimeout(250);

    const scrollAudit = await page.evaluate(() => {
      const shell = document.getElementById("eloryGlobalStickyShell");
      const audit = window.__eloryNotchAudit;
      const heights = [shell.getBoundingClientRect().height, ...audit.toggles.map(x => x.shellHeight), ...audit.samples.map(x => x.shellHeight)];
      const minHeight = Math.min(...heights);
      const maxHeight = Math.max(...heights);
      const documentHeights = [...audit.toggles.map(x => x.documentHeight), ...audit.samples.map(x => x.documentHeight)];
      const transitionShifts = audit.layoutShifts.filter(entry =>
        audit.toggles.some(toggle => entry.startTime >= toggle.time && entry.startTime <= toggle.time + 800)
      );
      const navTransitionShifts = transitionShifts.filter(entry =>
        entry.sources.some(source => source.node.includes("nav.elory-reference-nav"))
      );
      return {
        toggles: audit.toggles,
        samples: audit.samples,
        shellHeightDelta: maxHeight - minHeight,
        documentHeightDelta: documentHeights.length ? Math.max(...documentHeights) - Math.min(...documentHeights) : 0,
        cls: audit.cls,
        layoutShifts: audit.layoutShifts,
        transitionCLS: transitionShifts.reduce((sum, entry) => sum + entry.value, 0),
        fullNavTransitionCLS: navTransitionShifts.reduce((sum, entry) => sum + entry.value, 0),
        fullNavTransitionShiftCount: navTransitionShifts.length,
        frameGapCountOver34ms: audit.frameGaps.length,
        maxFrameGapMs: audit.frameGaps.length ? Math.max(...audit.frameGaps) : 0,
        documentHeight: document.documentElement.scrollHeight,
        maxScroll: Math.max(0, document.documentElement.scrollHeight - innerHeight)
      };
    });

    console.log("SLOW_SCROLL_AUDIT " + JSON.stringify(scrollAudit));
    assert.equal(scrollAudit.toggles.length, 4, "two slow down/up cycles should produce exactly four compact-state transitions");
    assert.ok(scrollAudit.shellHeightDelta <= 1, "header shell height must not change when compact mode toggles");
    assert.ok(scrollAudit.fullNavTransitionCLS < 0.005, "the original full navigation must not shift when the notch appears or disappears");
    assert.ok(scrollAudit.toggles.filter(x => x.compact).every(x => x.scrollY >= 88), "compact mode must engage only after its enter threshold");
    assert.ok(scrollAudit.toggles.filter(x => !x.compact).every(x => x.scrollY <= 48), "full header must return only after the exit threshold");

    await page.evaluate(() => window.scrollTo(0, 180));
    await page.waitForTimeout(350);
    const notch = await page.evaluate(async () => {
      const shell = document.getElementById("eloryGlobalStickyShell");
      const fullNav = shell.querySelector(":scope > .elory-reference-nav");
      const nav = shell.querySelector(":scope > .elory-notch-overlay");
      const fullNavBox = fullNav.getBoundingClientRect();
      const beam = nav.querySelector(".elory-notch-beam");
      const beamPath = nav.querySelector(".elory-notch-beam-path");
      const buttons = nav.querySelectorAll(".elory-mobile-notch .elory-notch-action");
      const before = parseFloat(getComputedStyle(beamPath).strokeDashoffset);
      await new Promise(resolve => setTimeout(resolve, 450));
      const after = parseFloat(getComputedStyle(beamPath).strokeDashoffset);
      const navBox = nav.getBoundingClientRect();
      const beamBox = beam.getBoundingClientRect();
      return {
        compact: shell.classList.contains("elory-notch-compact"),
        navPosition: getComputedStyle(nav).position,
        navWidth: navBox.width,
        navHeight: navBox.height,
        fullNavVisibility: getComputedStyle(fullNav).visibility,
        fullNavWidth: fullNavBox.width,
        fullNavHeight: fullNavBox.height,
        fullNavSizeStable: Math.abs(fullNavBox.width - window.__eloryStartNavSize.width) <= 1 &&
          Math.abs(fullNavBox.height - window.__eloryStartNavSize.height) <= 1,
        buttonCount: buttons.length,
        beamExists: !!beamPath,
        beamDashOffsetChanged: Number.isFinite(before) && Number.isFinite(after) && Math.abs(after - before) > 5,
        beamBox: { left: beamBox.left, top: beamBox.top, width: beamBox.width, height: beamBox.height },
        navBox: { left: navBox.left, top: navBox.top, width: navBox.width, height: navBox.height },
        beamOffset: { left: beamBox.left-navBox.left, top: beamBox.top-navBox.top, width: beamBox.width-navBox.width, height: beamBox.height-navBox.height },
        beamBoxAligned: Math.abs(beamBox.left - navBox.left) <= 1 && Math.abs(beamBox.top - navBox.top) <= 1 &&
          Math.abs(beamBox.width - navBox.width) <= 1 && Math.abs(beamBox.height - navBox.height) <= 1,
        strokeDasharray: getComputedStyle(beamPath).strokeDasharray
      };
    });
    await page.screenshot({ path: path.join(reportDir, "elory-notch-mobile-390x844.png"), fullPage: false });
    console.log("NOTCH_GEOMETRY " + JSON.stringify(notch));
    assert.equal(notch.compact, true, "notch must be visible when scrolling");
    assert.equal(notch.navPosition, "fixed", "the independent notch overlay must be fixed");
    assert.equal(notch.fullNavVisibility, "hidden", "the original navigation must hide without leaving normal flow");
    assert.equal(notch.fullNavSizeStable, true, "the original navigation dimensions must remain unchanged");
    assert.equal(notch.buttonCount, 3, "notch must retain exactly three actions");
    assert.equal(notch.beamExists, true, "SVG perimeter beam must exist");
    assert.equal(notch.beamDashOffsetChanged, true, "beam dash must move along the edge");
    assert.equal(notch.beamBoxAligned, true, "beam SVG must align with the notch border");

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(reportDir, "elory-header-mobile-390x844.png"), fullPage: false });

    const report = {
      status: "passed",
      viewport: start.viewport,
      start,
      slowScroll: scrollAudit,
      notch,
      pageErrors
    };
    fs.writeFileSync(path.join(reportDir, "notch-regression.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
