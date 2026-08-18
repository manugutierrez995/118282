import { test, expect } from "@playwright/test";

const PUBLIC_ID = "1199999";
const SLUG = "Chu_Berozu_decensored";

test("direct public ID opens through the existing landing reader flow", async ({ page }) => {
    const response = await page.goto(
        `http://127.0.0.1:4173/${PUBLIC_ID}`,
        { waitUntil: "domcontentloaded" }
    );

    expect(response?.ok()).toBeTruthy();
    await expect(page).toHaveURL(`http://127.0.0.1:4173/${PUBLIC_ID}`);
    await expect(page.locator(".landing-search")).toBeVisible();
    await expect(page.locator(".landing-rotunda")).toBeVisible();
    await expect(page.locator("#chapter-start")).toBeAttached({ timeout: 15000 });
    await expect(page.locator(".reader-page").first()).toBeAttached({ timeout: 15000 });
    await expect(page.locator("body")).toHaveClass(/reader-active/);
});

test("legacy direct slug remains compatible and canonicalizes to the public ID", async ({ page }) => {
    const response = await page.goto(
        `http://127.0.0.1:4173/${SLUG}`,
        { waitUntil: "domcontentloaded" }
    );

    expect(response?.ok()).toBeTruthy();
    await expect(page).toHaveURL(`http://127.0.0.1:4173/${PUBLIC_ID}`);
    await expect(page.locator("#chapter-start")).toBeAttached({ timeout: 15000 });
    await expect(page.locator(".reader-page").first()).toBeAttached({ timeout: 15000 });
    await expect(page.locator("body")).toHaveClass(/reader-active/);
});

test("the generic open-reader flow exposes the public ID without rerouting", async ({ page }) => {
    const response = await page.goto(
        "http://127.0.0.1:4173/",
        { waitUntil: "domcontentloaded" }
    );

    expect(response?.ok()).toBeTruthy();
    await expect(page.locator(".landing-search")).toBeVisible();
    await expect(page.locator(".landing-rotunda")).toBeVisible();

    await page.evaluate(({ slug }) => {
        window.dispatchEvent(new CustomEvent("open-reader", {
            detail: {
                source: "e",
                work: slug,
                chapter: "chapter_1"
            }
        }));
    }, { slug: SLUG });

    await expect(page).toHaveURL(`http://127.0.0.1:4173/${PUBLIC_ID}`);
    await expect(page.locator("#chapter-start")).toBeAttached({ timeout: 15000 });
    await expect(page.locator(".reader-page").first()).toBeAttached({ timeout: 15000 });
    await expect(page.locator("body")).toHaveClass(/reader-active/);
});
