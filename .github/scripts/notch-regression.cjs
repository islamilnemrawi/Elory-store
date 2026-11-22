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
    hasTouch: true,
    reducedMotion: "no-preference"
  });
  page.setDefaultTimeout(20000);
  const pageErrors = [];
  page.on("pageerror", error => pageErrors.push({ message: error.message, stack: error.stack }));

  try {
    await page.goto("http://127.0.0.1:4173/index.html", { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.locator("#eloryGlobalStickyShell").waitFor();
    const firstPaintHero = await page.evaluate(() => {
      const hero = document.getElementById("heroSlider");
      const style = hero ? getComputedStyle(hero) : null;
      return { exists: !!hero, opacity: style?.opacity, visibility: style?.visibility, pointerEvents: style?.pointerEvents, height: hero?.getBoundingClientRect().height || 0 };
    });
    assert.equal(firstPaintHero.exists, true, "hero fallback must exist at first paint");
    assert.equal(Number(firstPaintHero.opacity), 1, "hero fallback must not remain hidden while CMS data loads");
    assert.equal(firstPaintHero.visibility, "visible", "hero fallback must be visible before campaign data resolves");
    assert.ok(firstPaintHero.height >= 240, "hero must reserve its normal layout height during first paint");
    console.log("FIRST_PAINT_HERO " + JSON.stringify(firstPaintHero));
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
        maxScroll: Math.max(0, document.documentElement.scrollHeight - innerHeight),
        navInner: (() => {
          const inner = fullNav.querySelector(".elory-reference-nav-inner");
          const box = inner.getBoundingClientRect();
          const orders = document.getElementById("ordersBtn").getBoundingClientRect();
          const style = getComputedStyle(inner);
          return {
            width: box.width,
            height: box.height,
            centerOffset: Math.abs((orders.left + orders.width / 2) - (box.left + box.width / 2)),
            background: style.backgroundImage + " " + style.backgroundColor,
            borderColor: style.borderTopColor,
            borderRadius: style.borderTopLeftRadius,
            gap: parseFloat(style.columnGap)
          };
        })(),
        ordersColor: getComputedStyle(document.getElementById("ordersBtn")).color,
        primeColor: getComputedStyle(document.getElementById("primeHeaderBtn")).color,
        searchLabelColor: getComputedStyle(document.querySelector("#eloryGlobalStickyShell>.elory-reference-nav .search-btn .elory-search-label")).color,
        beam: (() => {
          const svg = fullNav.querySelector(".elory-reference-nav-beam");
          const compactSvg = shell.querySelector(".elory-notch-beam");
          const path = svg?.querySelector(".elory-reference-nav-beam-path");
          return path ? {
            exists: true,
            tagName: path.tagName.toLowerCase(),
            rx: path.getAttribute("rx"),
            d: path.getAttribute("d"),
            dasharray: getComputedStyle(path).strokeDasharray,
            stroke: getComputedStyle(path).stroke,
            animation: getComputedStyle(path).animationName,
            linecap: getComputedStyle(path).strokeLinecap,
            wedgeExists: svg?.querySelectorAll(".elory-reference-nav-beam-comet-layer").length === 4,
            wedgeDuration: svg ? getComputedStyle(svg.querySelector(".elory-reference-nav-beam-comet-head")).animationDuration : null,
            bothStartStyle3: !!svg?.classList.contains("elory-beam-style-3") && !!compactSvg?.classList.contains("elory-beam-style-3")
          } : { exists: false };
        })()
      };
    });
    console.log("START_STATE " + JSON.stringify(start));
    assert.deepEqual(start.viewport, { width: 390, height: 844 }, "must run at a real 390x844 CSS viewport");
    assert.equal(start.scrollY, 0, "regression test must begin at page top");
    assert.equal(start.beam.bothStartStyle3, true, "both notch SVGs must start in the approved style before first paint");
    assert.equal(start.compact, false, "page must start in full-header state");
    assert.ok(start.navInner.width < start.viewport.width - 12, "large navigation must render as a separate centered notch, not a full-width strip");
    assert.ok(start.navInner.height >= 50, "large navigation notch must have a substantial capsule height");
    assert.ok(start.navInner.centerOffset <= 2, "Orders label must be centered in the large notch");
    assert.ok(start.navInner.gap <= 8, "large notch actions must have compact spacing");
    assert.ok(start.navInner.borderRadius.includes("px") && parseFloat(start.navInner.borderRadius) >= 24,
      "large notch must have a true rounded capsule edge");
    assert.notEqual(start.navInner.borderColor, "rgba(0, 0, 0, 0)",
      "large notch border must remain visible with a soft blush edge");
    assert.match(start.navInner.background, /255,\s*248,\s*250/i, "large notch background must use the current Elory soft-pink surface");
    assert.match(start.navInner.background, /246,\s*221,\s*230/i, "large notch background must retain the current Elory pink mid-tone");
    assert.equal(start.ordersColor, start.primeColor, "Orders and Prime labels must share the active brand text color");
    assert.equal(start.searchLabelColor, start.primeColor, "Search label and header labels must share the active brand text color");
    
    const fullBeamStyles = [];
    for (let style = 1; style <= 4; style++) {
      await page.evaluate(styleNumber => {
        const shell = document.getElementById("eloryGlobalStickyShell");
        shell.querySelectorAll(".elory-reference-nav-beam,.elory-notch-beam").forEach(svg => {
          svg.classList.remove("elory-beam-style-1","elory-beam-style-2","elory-beam-style-3","elory-beam-style-4");
          svg.classList.add("elory-beam-style-" + styleNumber);
          svg.dataset.beamStyle = String(styleNumber);
        });
      }, style);
      await page.waitForTimeout(180);
      await page.screenshot({path:path.join(reportDir,"elory-beam-style-"+style+"-full.png"),fullPage:false});
      fullBeamStyles.push(await page.evaluate(() => {
        const svg=document.querySelector("#eloryGlobalStickyShell>.elory-reference-nav .elory-reference-nav-beam");
        return {style:svg.dataset.beamStyle,secondaryOpacity:getComputedStyle(svg.querySelector(".elory-reference-nav-beam-secondary-head")).opacity,
          ringOpacity:getComputedStyle(svg.querySelector(".elory-reference-nav-beam-ring")).opacity,
          glowOpacity:getComputedStyle(svg.querySelector(".elory-reference-nav-beam-comet-glow")).opacity,
          midOpacity:getComputedStyle(svg.querySelector(".elory-reference-nav-beam-comet-mid")).opacity,
          headOpacity:getComputedStyle(svg.querySelector(".elory-reference-nav-beam-comet-head")).opacity,
          headStroke:getComputedStyle(svg.querySelector(".elory-reference-nav-beam-comet-head")).stroke,
          glowWidth:getComputedStyle(svg.querySelector(".elory-reference-nav-beam-comet-glow")).strokeWidth,duration:getComputedStyle(svg.querySelector(".elory-reference-nav-beam-comet-head")).animationDuration};
      }));
    }
    assert.deepEqual(fullBeamStyles.map(x=>x.style),["1","2","3","4"],"all four full-size lighting styles must be independently selectable");
    assert.deepEqual(fullBeamStyles.map(x=>x.duration),["18s","18s","18s","18s"],"all four full-size styles must share one continuous animation pace");
    assert.ok(Number(fullBeamStyles[1].secondaryOpacity)>0,"style 2 must show its opposing second comet");
    assert.ok(Number(fullBeamStyles[2].ringOpacity)>0,"style 3 must show one visible perimeter halo");
    assert.equal(Number(fullBeamStyles[2].glowOpacity),0,"style 3 must not stack a second glow dash");
    assert.equal(Number(fullBeamStyles[2].midOpacity),0,"style 3 must not stack a second mid dash");
    assert.match(fullBeamStyles[2].headStroke,/246, 184, 206/,"style 3 moving glint must remain Elory blush pink");
    await page.evaluate(() => document.querySelectorAll(".elory-reference-nav-beam,.elory-notch-beam").forEach(svg=>svg.classList.add("elory-beam-style-3")));
    await page.emulateMedia({ reducedMotion: "reduce" });
    const reducedFull = await page.evaluate(() => ({ring:getComputedStyle(document.querySelector(".elory-reference-nav-beam-ring")).opacity,head:getComputedStyle(document.querySelector(".elory-reference-nav-beam-comet-head")).opacity}));
    assert.ok(Number(reducedFull.ring)>=.9,"large notch halo must remain visible with reduced motion");
    assert.equal(Number(reducedFull.head),0,"large notch must not freeze a glint at the upper-left path origin");
    await page.emulateMedia({ reducedMotion: "no-preference" });
    assert.ok(parseFloat(fullBeamStyles[3].glowWidth)>parseFloat(fullBeamStyles[0].glowWidth),"style 4 must have a visibly broader aurora ribbon");

    const largeBeamMotion = await page.evaluate(async () => {
      const path = document.querySelector("#eloryGlobalStickyShell>.elory-reference-nav .elory-reference-nav-beam-path");
      const head = document.querySelector("#eloryGlobalStickyShell>.elory-reference-nav .elory-reference-nav-beam-comet-head");
      const before = parseFloat(getComputedStyle(path).strokeDashoffset);
      const beforeHead = parseFloat(getComputedStyle(head).strokeDashoffset);
      await new Promise(resolve => setTimeout(resolve, 450));
      const after = parseFloat(getComputedStyle(path).strokeDashoffset);
      const afterHead = parseFloat(getComputedStyle(head).strokeDashoffset);
      const wedgeMoved = Number.isFinite(beforeHead) && Number.isFinite(afterHead) && Math.abs(afterHead-beforeHead)>5;
      return { before, after, changed: Number.isFinite(before) && Number.isFinite(after) && Math.abs(after - before) > 5, wedgeMoved };
    });
    console.log("LARGE_BEAM_MOTION " + JSON.stringify(largeBeamMotion));
    assert.equal(largeBeamMotion.changed, true, "large notch perimeter timing track must advance");
    assert.equal(largeBeamMotion.wedgeMoved, true, "large luminous comet must visibly move along the capsule perimeter");
    assert.equal(start.beam.exists, true, "large notch must have its own perimeter beam");
    assert.equal(start.beam.tagName, "rect", "large notch beam must trace the complete capsule perimeter like the compact notch");
    assert.ok(Number(start.beam.rx) >= 24, "large notch beam must follow a fully rounded capsule edge");
    assert.notEqual(start.beam.animation, "none", "large notch beam must remain animated even when reduced motion is requested");
    assert.ok(start.beam.dasharray.includes("118") && start.beam.dasharray.includes("882"), "large notch retains its invisible perimeter timing track");
    assert.equal(start.beam.wedgeExists, true, "large notch must render its luminous tapered comet");

    assert.equal(start.shellPosition, "relative", "the full header shell must not be a large sticky repaint layer");
    assert.ok(start.maxScroll > 300, "page needs enough scroll range for the regression test");
    await page.evaluate(size => { window.__eloryStartNavSize = size; }, start.fullNavSize);

    // Full navigation search: labeled launcher, dedicated close action, magnifier submits.
    const headerSearch = page.locator("#eloryGlobalStickyShell > .elory-reference-nav");
    const headerSearchButton = page.locator("#eloryHeaderSearchButton");
    const headerSearchClose = page.locator("#eloryHeaderSearchCloseButton");
    assert.equal(await headerSearchButton.locator(".elory-search-label").innerText(), "البحث",
      "full navigation closed state must show the search label beside the magnifier");
    await headerSearchButton.click();
    await page.waitForTimeout(250);
    assert.equal(await headerSearch.evaluate(el => el.classList.contains("elory-header-search-open")), true,
      "full navigation search launcher must expand the search field");
    assert.equal(await page.locator("#primeHeaderBtn").isVisible(), false, "Prime must hide while full-nav search is open");
    assert.equal(await page.locator("#ordersBtn").isVisible(), false, "Orders must hide while full-nav search is open");
    assert.equal(await page.locator("#searchInput").isVisible(), true, "full-nav search input must occupy the navigation");
    assert.equal(await headerSearchClose.isVisible(), true, "full-nav search must show a dedicated close button");
    await page.locator("#searchInput").fill("اختبار");
    await headerSearchClose.click();
    await page.waitForTimeout(250);
    assert.equal(await headerSearch.evaluate(el => el.classList.contains("elory-header-search-open")), false,
      "dedicated close button must collapse full navigation search");
    assert.equal(await page.locator("#primeHeaderBtn").isVisible(), true, "Prime must return after closing full-nav search");
    assert.equal(await page.locator("#ordersBtn").isVisible(), true, "Orders must return after closing full-nav search");
    assert.equal(await page.locator("#searchInput").isVisible(), false, "full-nav search input must collapse");
    await headerSearchButton.click();
    await page.locator("#searchInput").fill("اختبار");
    await headerSearchButton.click();
    await page.waitForTimeout(300);
    assert.equal(await headerSearch.evaluate(el => el.classList.contains("elory-header-search-open")), false,
      "full navigation magnifier must submit and close search when a query is entered");


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
                  const name = node && node.tagName ? node.tagName.toLowerCase() +
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

    await page.evaluate(() => {
      const shell=document.getElementById("eloryGlobalStickyShell");
      shell.querySelectorAll(".elory-reference-nav-beam,.elory-notch-beam").forEach(svg=>{
        svg.classList.remove("elory-beam-style-1","elory-beam-style-2","elory-beam-style-4");
        svg.classList.add("elory-beam-style-3");
        svg.dataset.beamStyle="3";
      });
    });
    await page.evaluate(() => window.scrollTo(0, 180));
    await page.waitForTimeout(350);
    const fixedStyleAfterScroll = await page.evaluate(() => {
      const shell=document.getElementById("eloryGlobalStickyShell");
      const full=shell.querySelector(".elory-reference-nav-beam");
      const compact=shell.querySelector(".elory-notch-beam");
      return {full:full.dataset.beamStyle,compact:compact.dataset.beamStyle};
    });
    assert.equal(fixedStyleAfterScroll.full,"3","the approved breathing-halo style must remain fixed during scrolling");
    assert.equal(fixedStyleAfterScroll.compact,"3","the compact notch must retain the same approved style");
    const notch = await page.evaluate(async () => {
      const shell = document.getElementById("eloryGlobalStickyShell");
      const fullNav = shell.querySelector(":scope > .elory-reference-nav");
      const nav = shell.querySelector(":scope > .elory-notch-overlay");
      const fullNavBox = fullNav.getBoundingClientRect();
      const beam = nav.querySelector(".elory-notch-beam");
      const beamPath = nav.querySelector(".elory-notch-beam-path");
      const beamWedge = nav.querySelector(".elory-notch-beam-comet-head");
      const cometLayers = nav.querySelectorAll(".elory-notch-beam-comet-layer");
      const buttons = nav.querySelectorAll(".elory-mobile-notch .elory-notch-action:not(.elory-notch-search-close)");
      const cartCenter = document.getElementById("eloryNotchCart").getBoundingClientRect().left +
        document.getElementById("eloryNotchCart").getBoundingClientRect().width / 2;
      const favoriteCenter = document.getElementById("eloryNotchFavorites").getBoundingClientRect().left +
        document.getElementById("eloryNotchFavorites").getBoundingClientRect().width / 2;
      const searchCenter = document.getElementById("eloryNotchSearchButton").getBoundingClientRect().left +
        document.getElementById("eloryNotchSearchButton").getBoundingClientRect().width / 2;
      const before = parseFloat(getComputedStyle(beamPath).strokeDashoffset);
      const beforeWedgeOffset = parseFloat(getComputedStyle(beamWedge).strokeDashoffset);
      await new Promise(resolve => setTimeout(resolve, 450));
      const after = parseFloat(getComputedStyle(beamPath).strokeDashoffset);
      const afterWedgeOffset = parseFloat(getComputedStyle(beamWedge).strokeDashoffset);
      const wedgeMoved = Number.isFinite(beforeWedgeOffset) && Number.isFinite(afterWedgeOffset) && Math.abs(afterWedgeOffset-beforeWedgeOffset)>5;
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
        actionOrderCorrect: cartCenter > favoriteCenter && favoriteCenter > searchCenter,
        searchLabelHidden: getComputedStyle(document.querySelector(".elory-notch-search-label")).display === "none",
        beamExists: !!beamPath,
        beamDashOffsetChanged: Number.isFinite(before) && Number.isFinite(after) && Math.abs(after - before) > 5,
        wedgeExists: cometLayers.length === 4,
        wedgeDuration: getComputedStyle(beamWedge).animationDuration,
        wedgeMoved,
        beamBox: { left: beamBox.left, top: beamBox.top, width: beamBox.width, height: beamBox.height },
        navBox: { left: navBox.left, top: navBox.top, width: navBox.width, height: navBox.height },
        beamOffset: { left: beamBox.left-navBox.left, top: beamBox.top-navBox.top, width: beamBox.width-navBox.width, height: beamBox.height-navBox.height },
        beamBoxAligned: Math.abs(beamBox.left - navBox.left) <= 1 && Math.abs(beamBox.top - navBox.top) <= 1 &&
          Math.abs(beamBox.width - navBox.width) <= 1 && Math.abs(beamBox.height - navBox.height) <= 1,
        strokeDasharray: getComputedStyle(beamPath).strokeDasharray,
        strokeLinecap: getComputedStyle(beamPath).strokeLinecap,
        cometStyles: Array.from(cometLayers).map(layer => { const s=getComputedStyle(layer); const r=layer.getBoundingClientRect(); return {className:layer.getAttribute("class"),stroke:s.stroke,strokeWidth:s.strokeWidth,strokeDasharray:s.strokeDasharray,strokeDashoffset:s.strokeDashoffset,animationName:s.animationName,animationDuration:s.animationDuration,opacity:s.opacity,filter:s.filter,box:{x:r.x,y:r.y,width:r.width,height:r.height}}; })
      };
    });
    await page.screenshot({ path: path.join(reportDir, "elory-notch-mobile-390x844.png"), fullPage: false });
    console.log("NOTCH_GEOMETRY " + JSON.stringify(notch));
    assert.equal(notch.compact, true, "notch must be visible when scrolling");
    assert.equal(notch.navPosition, "fixed", "the independent notch overlay must be fixed");
    assert.equal(notch.fullNavVisibility, "hidden", "the original navigation must hide without leaving normal flow");
    assert.equal(notch.fullNavSizeStable, true, "the original navigation dimensions must remain unchanged");
    assert.equal(notch.buttonCount, 3, "notch must retain exactly three visible actions");
    assert.equal(notch.actionOrderCorrect, true, "notch actions must be ordered cart right, favorites center, search left");
    assert.equal(notch.searchLabelHidden, true, "compact notch must show the magnifier icon without a text label");
    assert.equal(notch.beamExists, true, "SVG perimeter beam must exist");
    assert.equal(notch.beamDashOffsetChanged, true, "compact notch timing track must move even when reduced motion is requested");
    assert.equal(notch.wedgeExists, true, "compact notch must render its luminous tapered comet");

    assert.equal(notch.wedgeMoved, true, "compact luminous comet must visibly move along the capsule perimeter");
    assert.equal(notch.strokeLinecap, "round", "compact notch beam must have rounded head and tail");
    assert.equal(notch.beamBoxAligned, true, "beam SVG must align with the notch border");

    const compactBeamStyles = [];
    for (let style = 1; style <= 4; style++) {
      await page.evaluate(styleNumber => {
        const shell = document.getElementById("eloryGlobalStickyShell");
        shell.querySelectorAll(".elory-reference-nav-beam,.elory-notch-beam").forEach(svg => {
          svg.classList.remove("elory-beam-style-1","elory-beam-style-2","elory-beam-style-3","elory-beam-style-4");
          svg.classList.add("elory-beam-style-" + styleNumber);
          svg.dataset.beamStyle = String(styleNumber);
        });
      }, style);
      await page.waitForTimeout(180);
      await page.screenshot({path:path.join(reportDir,"elory-beam-style-"+style+"-compact.png"),fullPage:false});
      compactBeamStyles.push(await page.evaluate(() => {
        const shell=document.getElementById("eloryGlobalStickyShell");
        const full=shell.querySelector(".elory-reference-nav-beam");
        const compact=shell.querySelector(".elory-notch-beam");
        return {full:full.dataset.beamStyle,compact:compact.dataset.beamStyle,
          secondaryOpacity:getComputedStyle(compact.querySelector(".elory-notch-beam-secondary-head")).opacity,
          ringOpacity:getComputedStyle(compact.querySelector(".elory-notch-beam-ring")).opacity,
          glowOpacity:getComputedStyle(compact.querySelector(".elory-notch-beam-comet-glow")).opacity,
          midOpacity:getComputedStyle(compact.querySelector(".elory-notch-beam-comet-mid")).opacity,
          headOpacity:getComputedStyle(compact.querySelector(".elory-notch-beam-comet-head")).opacity,
          headStroke:getComputedStyle(compact.querySelector(".elory-notch-beam-comet-head")).stroke,
          glowWidth:getComputedStyle(compact.querySelector(".elory-notch-beam-comet-glow")).strokeWidth,duration:getComputedStyle(compact.querySelector(".elory-notch-beam-comet-head")).animationDuration};
      }));
    }
    assert.deepEqual(compactBeamStyles.map(x=>x.compact),["1","2","3","4"],"all four compact-notch lighting styles must be independently selectable");
    assert.deepEqual(compactBeamStyles.map(x=>x.duration),["18s","18s","18s","18s"],"all four compact styles must share one continuous animation pace");
    assert.ok(compactBeamStyles.every(x=>x.full===x.compact),"large and compact notches must always use the same selected style");
    assert.ok(Number(compactBeamStyles[1].secondaryOpacity)>0,"compact style 2 must show its opposing second comet");
    assert.ok(Number(compactBeamStyles[2].ringOpacity)>0,"compact style 3 must show one visible perimeter halo");
    assert.equal(Number(compactBeamStyles[2].glowOpacity),0,"compact style 3 must not stack a second glow dash");
    assert.equal(Number(compactBeamStyles[2].midOpacity),0,"compact style 3 must not stack a second mid dash");
    assert.match(compactBeamStyles[2].headStroke,/246, 184, 206/,"compact style 3 moving glint must remain Elory blush pink");
    await page.evaluate(() => document.querySelectorAll(".elory-reference-nav-beam,.elory-notch-beam").forEach(svg=>svg.classList.add("elory-beam-style-3")));
    await page.emulateMedia({ reducedMotion: "reduce" });
    const reducedCompact = await page.evaluate(() => ({ring:getComputedStyle(document.querySelector(".elory-notch-beam-ring")).opacity,head:getComputedStyle(document.querySelector(".elory-notch-beam-comet-head")).opacity}));
    assert.ok(Number(reducedCompact.ring)>=.9,"compact notch halo must remain visible with reduced motion");
    assert.equal(Number(reducedCompact.head),0,"compact notch must not freeze a glint at the upper-left path origin");
    await page.emulateMedia({ reducedMotion: "no-preference" });
    assert.ok(parseFloat(compactBeamStyles[3].glowWidth)>parseFloat(compactBeamStyles[0].glowWidth),"compact style 4 must have a visibly broader aurora ribbon");

    const compactSearchButton = page.locator("#eloryNotchSearchButton");
    const compactSearchClose = page.locator("#eloryNotchSearchCloseButton");
    await compactSearchButton.click();
    await page.waitForTimeout(250);
    assert.equal(await page.locator("#eloryGlobalStickyShell").evaluate(el => el.classList.contains("elory-notch-search-open")), true,
      "compact notch search launcher must expand the input");
    assert.equal(await page.locator("#eloryNotchCart").isVisible(), false, "cart action must yield the full notch to search");
    assert.equal(await page.locator("#eloryNotchFavorites").isVisible(), false, "favorites action must yield the full notch to search");
    assert.equal(await page.locator("#eloryNotchSearchInput").isVisible(), true, "compact search input must fill the notch");
    assert.equal(await compactSearchClose.isVisible(), true, "compact search must show a dedicated close button");
    await page.locator("#eloryNotchSearchInput").fill("اختبار");
    await page.waitForTimeout(300);
    assert.equal(await page.locator("#searchInput").inputValue(), "اختبار",
      "compact input must feed the existing live product-search suggestion engine");
    await compactSearchClose.click();
    await page.waitForTimeout(250);
    assert.equal(await page.locator("#eloryGlobalStickyShell").evaluate(el => el.classList.contains("elory-notch-search-open")), false,
      "dedicated close button must collapse compact search");
    assert.equal(await page.locator("#eloryNotchCart").isVisible(), true, "cart action must return after closing search");
    assert.equal(await page.locator("#eloryNotchFavorites").isVisible(), true, "favorites action must return after closing search");
    await compactSearchButton.click();
    await page.locator("#eloryNotchSearchInput").fill("اختبار");
    await compactSearchButton.click();
    await page.waitForTimeout(300);
    assert.equal(await page.locator("#eloryGlobalStickyShell").evaluate(el => el.classList.contains("elory-notch-search-open")), false,
      "compact magnifier must submit and close search when a query is entered");

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(reportDir, "elory-header-mobile-390x844.png"), fullPage: false });

    const report = {
      beamStyles: { full: fullBeamStyles, compact: compactBeamStyles, fixedStyleAfterScroll },
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
