const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");
const OUT = path.join(process.cwd(), "reports", "storefront-audit");
fs.mkdirSync(OUT, { recursive: true });
const targets = [
  { name: "branch-preview", url: process.env.AUDIT_URL },
  { name: "production", url: process.env.PRODUCTION_URL }
].filter(x => x.url);
const viewports = [
  { name: "mobile-390x844", width: 390, height: 844, isMobile: true, hasTouch: true },
  { name: "desktop-1365x900", width: 1365, height: 900, isMobile: false, hasTouch: false }
];
const blockedAction = /طلب|شراء|تأكيد|دفع|الدفع|إتمام|إرسال|حذف|مسح|إلغاء الطلب|تسجيل خروج|خروج|pay|checkout|place order|submit order|delete|remove|logout|sign out|confirm order/i;
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function inspectTarget(browser, target, viewport) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 1, isMobile: viewport.isMobile, hasTouch: viewport.hasTouch
  });
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  const errors = { page: [], console: [], failedRequests: [], badResponses: [] };
  page.on("pageerror", e => errors.page.push({ message: e.message, stack: e.stack }));
  page.on("console", msg => { if (msg.type() === "error") errors.console.push({ text: msg.text().slice(0, 600) }); });
  page.on("requestfailed", req => errors.failedRequests.push({ url: req.url(), method: req.method(), error: req.failure()?.errorText || "unknown" }));
  page.on("response", res => { if (res.status() >= 400) errors.badResponses.push({ status: res.status(), url: res.url(), method: res.request().method() }); });
  const result = {
    target: target.name, url: target.url, viewport: viewport.name,
    loaded: false, title: null, finalUrl: null, counts: {}, layout: {},
    images: [], internalLinks: [], testedButtons: [], skippedButtons: [], testedLinks: [], errors
  };
  try {
    const response = await page.goto(target.url, { waitUntil: "domcontentloaded", timeout: 60000 });
    result.httpStatus = response?.status() ?? null;
    await wait(5000);
    result.loaded = !!response && response.status() < 400;
    result.title = await page.title();
    result.finalUrl = page.url();
    result.layout = await page.evaluate(() => {
      const doc = document.documentElement, body = document.body;
      const visible = el => { const s = getComputedStyle(el), r = el.getBoundingClientRect(); return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0; };
      const images = [...document.images].map(img => ({
        src: img.currentSrc || img.src, alt: img.alt || "", loaded: img.complete && img.naturalWidth > 0,
        naturalWidth: img.naturalWidth, width: Math.round(img.getBoundingClientRect().width), height: Math.round(img.getBoundingClientRect().height)
      }));
      const links = [...document.querySelectorAll("a[href]")].map(a => ({
        text: (a.innerText || a.getAttribute("aria-label") || a.title || "").trim().replace(/\s+/g, " ").slice(0, 100),
        href: a.href, target: a.target || ""
      }));
      return {
        viewport: { width: innerWidth, height: innerHeight },
        document: { width: doc.scrollWidth, height: doc.scrollHeight, bodyWidth: body.scrollWidth },
        horizontalOverflow: doc.scrollWidth > innerWidth + 2 || body.scrollWidth > innerWidth + 2,
        visibleButtons: [...document.querySelectorAll("button,[role=button]")].filter(visible).length,
        allButtons: document.querySelectorAll("button,[role=button]").length,
        visibleInputs: [...document.querySelectorAll("input,select,textarea")].filter(visible).length,
        allInputs: document.querySelectorAll("input,select,textarea").length,
        visibleAnchors: [...document.querySelectorAll("a[href]")].filter(visible).length,
        allAnchors: document.querySelectorAll("a[href]").length,
        visibleSections: [...document.querySelectorAll("main,section")].filter(visible).map(el => ({ tag: el.tagName, id: el.id || "", className: typeof el.className === "string" ? el.className.slice(0, 100) : "" })),
        images, links
      };
    });
    result.counts = { buttons: result.layout.allButtons, inputs: result.layout.allInputs, anchors: result.layout.allAnchors, sections: result.layout.visibleSections.length };
    result.images = result.layout.images.filter(x => !x.loaded && x.src && !x.src.startsWith("data:"));
    result.internalLinks = result.layout.links.filter(x => { try { return new URL(x.href).origin === new URL(target.url).origin; } catch { return false; } });
    await page.screenshot({ path: path.join(OUT, target.name + "-" + viewport.name + "-top.png"), fullPage: false });
    await page.screenshot({ path: path.join(OUT, target.name + "-" + viewport.name + "-full.png"), fullPage: true, animations: "disabled" });

    const buttonMeta = await page.locator("button,[role=button]").evaluateAll(els => els.map((el, index) => ({
      index, text: (el.innerText || el.getAttribute("aria-label") || el.title || "").trim().replace(/\s+/g, " ").slice(0, 100),
      aria: el.getAttribute("aria-label") || "", title: el.title || "", type: el.getAttribute("type") || "",
      disabled: !!el.disabled, visible: (() => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden"; })(),
      inForm: !!el.closest("form"), id: el.id || ""
    })));
    // Do not click arbitrary storefront controls: many buttons trigger cart, auth,
    // navigation, or third-party flows. Inventory them without changing user state.
    result.buttonInventory = buttonMeta.map(b => ({
      ...b,
      action: b.type === "submit" || b.inForm || blockedAction.test([b.text, b.aria, b.title, b.id].join(" "))
        ? "sensitive-or-form"
        : "requires-dedicated-functional-test"
    }));
    result.skippedButtons = result.buttonInventory.map(b => ({
      index: b.index, text: b.text, id: b.id,
      reason: "not clicked by the non-destructive audit"
    }));
    const base = new URL(target.url);
    const hrefs = [...new Set(result.internalLinks.map(x => x.href).filter(h => {
      try {
        const u = new URL(h);
        return u.origin === base.origin && (u.pathname !== base.pathname || u.search !== base.search) &&
          !blockedAction.test(u.pathname + " " + u.search);
      } catch { return false; }
    }))].slice(0, 80);
    for (const href of hrefs) {
      try {
        const res = await context.request.get(href, { timeout: 15000 });
        result.testedLinks.push({ href, status: res.status(), result: res.ok() ? "loaded" : "http-error" });
      } catch (e) {
        result.testedLinks.push({ href, result: "request-failed", error: String(e).slice(0, 300) });
      }
    }
  } catch (e) { result.fatalError = String(e).slice(0, 1000); }
  finally { await context.close(); }
  return result;
}
(async () => {
  const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage"] });
  const results = [];
  try {
    for (const target of targets) for (const viewport of viewports) results.push(await inspectTarget(browser, target, viewport));
  } finally { await browser.close(); }
  const summary = {
    generatedAt: new Date().toISOString(),
    targets: targets.map(t => ({ name: t.name, url: t.url })),
    runs: results.map(r => ({
      target: r.target, viewport: r.viewport, loaded: r.loaded, httpStatus: r.httpStatus,
      horizontalOverflow: r.layout?.horizontalOverflow, counts: r.counts,
      brokenImages: r.images?.length || 0, pageErrors: r.errors?.page?.length || 0,
      consoleErrors: r.errors?.console?.length || 0, failedRequests: r.errors?.failedRequests?.length || 0,
      badResponses: r.errors?.badResponses?.length || 0, testedButtons: r.testedButtons?.length || 0,
      failedButtonClicks: r.testedButtons?.filter(x => x.result === "failed").length || 0,
      skippedButtons: r.skippedButtons?.length || 0, testedLinks: r.testedLinks?.length || 0,
      failedLinks: r.testedLinks?.filter(x => x.result !== "loaded").length || 0, fatalError: r.fatalError || null
    }))
  };
  fs.writeFileSync(path.join(OUT, "storefront-audit.json"), JSON.stringify({ summary, results }, null, 2));
  fs.writeFileSync(path.join(OUT, "storefront-audit-summary.json"), JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
})().catch(e => { console.error(e); process.exitCode = 1; });
