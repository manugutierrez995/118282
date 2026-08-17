import { test, expect } from "@playwright/test";

test("direct work slug opens through the existing landing reader flow", async ({ page }) => {
    const response = await page.goto(
        "http://127.0.0.1:4173/Chu_Berozu_decensored",
        { waitUntil: "domcontentloaded" }
    );

    expect(response?.ok()).toBeTruthy();
    await expect(page.locator(".landing-search")).toBeVisible();
    await expect(page.locator(".landing-rotunda")).toBeVisible();
    await expect(page.locator("#chapter-start")).toBeAttached({ timeout: 15000 });
    await expect(page.locator(".reader-page").first()).toBeAttached({ timeout: 15000 });
    await expect(page.locator("body")).toHaveClass(/reader-active/);
});
