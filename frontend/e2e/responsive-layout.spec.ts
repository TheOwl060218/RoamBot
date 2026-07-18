import { expect, test } from '@playwright/test'

import { submitRecommendation } from './helpers'

test('form and results keep their intended responsive relationship', async ({ page }) => {
  await page.goto('/')
  await submitRecommendation(page)

  const form = await page.locator('.travel-form').boundingBox()
  const results = await page.locator('.results-panel').boundingBox()
  const viewport = page.viewportSize()
  expect(form).not.toBeNull()
  expect(results).not.toBeNull()
  expect(viewport).not.toBeNull()

  if (viewport!.width > 1040) {
    expect(form!.x + form!.width).toBeLessThanOrEqual(results!.x)
  } else {
    expect(form!.y + form!.height).toBeLessThanOrEqual(results!.y)
  }

  const dimensions = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    pageWidth: document.documentElement.scrollWidth,
  }))
  expect(dimensions.pageWidth).toBe(dimensions.viewportWidth)
})
