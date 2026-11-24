"use strict";

const assert = require("node:assert/strict");
const { chromium } = require("playwright");

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    const pageErrors = [];
    page.on("pageerror", error => pageErrors.push(error.message));

    const url = process.env.STOREFRONT_SECURITY_URL || "http://127.0.0.1:4173/index.html";
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForFunction(() =>
      typeof window.renderShopPills === "function" &&
      typeof window.renderCustomerOrderCard === "function" &&
      typeof window.bindCustomerOrderNavigation === "function",
      null,
      { timeout: 30000 }
    );

    const result = await page.evaluate(() => {
      const category = 'probe" onclick="window.__eloryXss=1';
      const productId = "probe');window.__eloryXss=1;//";
      window.__eloryXss = 0;
      window.__shopArgs = null;
      window.__openedProductId = null;

      window.showShopPage = (value, title) => {
        window.__shopArgs = [value, title];
      };
      window.openProductDetails = value => {
        window.__openedProductId = value;
      };

      storeCategories = [{ name: category, active: true, sort_order: 1 }];
      renderShopPills();
      const pill = [...document.querySelectorAll("#shopCategoryPills button[data-shop-category]")].find(button => button.dataset.shopCategory === category);
      const categoryInlineHandler = pill?.getAttribute("onclick") ?? null;
      const categoryValue = pill?.dataset.shopCategory ?? null;
      pill?.click();

      const holder = document.createElement("div");
      holder.innerHTML = renderCustomerOrderCard({
        items: [{ product_id: productId, name: "XSS regression probe", quantity: 1, price: 1 }]
      });
      bindCustomerOrderNavigation(holder);
      const orderButton = holder.querySelector("button.customer-order-item-open[data-product-id]");
      const orderInlineHandler = orderButton?.getAttribute("onclick") ?? null;
      const orderProductId = orderButton?.dataset.productId ?? null;
      orderButton?.click();

      return {
        categoryInlineHandler,
        categoryValue,
        shopArgs: window.__shopArgs,
        orderInlineHandler,
        orderProductId,
        openedProductId: window.__openedProductId,
        executed: window.__eloryXss
      };
    });

    assert.equal(result.categoryInlineHandler, null, "Category buttons must not contain inline JavaScript handlers");
    assert.equal(result.categoryValue, 'probe" onclick="window.__eloryXss=1');
    assert.deepEqual(result.shopArgs, ['probe" onclick="window.__eloryXss=1', 'probe" onclick="window.__eloryXss=1']);
    assert.equal(result.orderInlineHandler, null, "Customer-order product buttons must not contain inline JavaScript handlers");
    assert.equal(result.orderProductId, "probe');window.__eloryXss=1;//");
    assert.equal(result.openedProductId, "probe');window.__eloryXss=1;//", "Delegated navigation must preserve the product identifier");
    assert.equal(result.executed, 0, "Injected strings must never execute");
    assert.deepEqual(pageErrors, [], "The storefront must not emit uncaught page errors during the regression test");

    console.log("Stored-XSS regression passed: category names and customer-order product IDs remain data, not executable code.");
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
