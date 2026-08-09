import { expect, test } from '@playwright/test'

import { submitRecommendation } from './helpers'

test('form and results keep their intended responsive relationship', async ({ page }) => {
  await page.goto('/')

  const initialForm = await page.locator('.travel-form').boundingBox()
  const initialViewport = page.viewportSize()
  const initialContentWidth = await page.evaluate(() => document.documentElement.clientWidth)
  expect(initialForm).not.toBeNull()
  expect(initialViewport).not.toBeNull()
  expect(Math.abs(initialForm!.x + initialForm!.width / 2 - initialContentWidth / 2)).toBeLessThanOrEqual(8)

  const handles = await page.getByRole('slider').all()
  expect(handles).toHaveLength(2)
  for (const handle of handles) {
    const hitArea = await handle.boundingBox()
    expect(hitArea).not.toBeNull()
    expect(hitArea!.width).toBeGreaterThanOrEqual(44)
    expect(hitArea!.height).toBeGreaterThanOrEqual(44)
  }

  await page.getByRole('checkbox', { name: '博物馆', exact: true }).check()
  await submitRecommendation(page)

  const header = await page.locator('.shell-header').boundingBox()
  expect(header).not.toBeNull()
  await expect.poll(async () => {
    const box = await page.locator('.query-summary').boundingBox()
    return Math.abs((box?.y ?? 0) - (header!.height + 16))
  }).toBeLessThanOrEqual(4)
  await expect(page.locator('.travel-form')).toHaveCount(0)
  await expect(page.locator('.query-summary')).toHaveCount(1)

  const summary = await page.locator('.query-summary').boundingBox()
  const results = await page.locator('.results-panel').boundingBox()
  const candidates = await page.locator('.candidate-list').boundingBox()
  const detail = await page.locator('.place-detail').boundingBox()
  const viewport = page.viewportSize()
  expect(summary).not.toBeNull()
  expect(results).not.toBeNull()
  expect(candidates).not.toBeNull()
  expect(detail).not.toBeNull()
  expect(viewport).not.toBeNull()
  const summaryToResultsGap = results!.y - (summary!.y + summary!.height)
  const intendedGap = viewport!.width <= 600 ? 12 : 20
  expect(Math.abs(summaryToResultsGap - intendedGap)).toBeLessThanOrEqual(4)

  expect(Math.abs(summary!.y - (header!.height + 16))).toBeLessThanOrEqual(4)

  if (viewport!.width >= 1024) {
    expect(candidates!.x + candidates!.width).toBeLessThanOrEqual(detail!.x)
    const candidatePane = page.locator('.candidate-pane')
    const paneMetrics = await candidatePane.evaluate((element) => {
      const list = element.querySelector('.candidate-list') as HTMLElement
      const style = getComputedStyle(element)
      return {
        paneHeight: element.getBoundingClientRect().height,
        listHeight: list.getBoundingClientRect().height,
        overscrollBehaviorY: style.overscrollBehaviorY,
      }
    })
    expect(paneMetrics.paneHeight).toBeLessThanOrEqual(paneMetrics.listHeight + 32)
    expect(paneMetrics.overscrollBehaviorY).not.toBe('contain')
  } else {
    expect(candidates!.y + candidates!.height).toBeLessThanOrEqual(detail!.y)
  }

  const matchColumnCount = await page.locator('.match-grid').evaluate((element) => (
    getComputedStyle(element).gridTemplateColumns.split(' ').length
  ))
  expect(matchColumnCount).toBe(viewport!.width <= 600 ? 1 : 3)

  const weatherDate = await page.locator('.weather-day-heading time').first().boundingBox()
  const weatherCondition = await page.locator('.weather-condition').first().boundingBox()
  const weatherHeading = await page.locator('.weather-list-single .weather-day-heading').boundingBox()
  const weatherFacts = await page.locator('.weather-list-single .weather-facts').boundingBox()
  const weatherSummary = await page.locator('.weather-list-single .weather-summary').boundingBox()
  expect(weatherDate).not.toBeNull()
  expect(weatherCondition).not.toBeNull()
  expect(weatherHeading).not.toBeNull()
  expect(weatherFacts).not.toBeNull()
  expect(weatherSummary).not.toBeNull()
  expect(weatherCondition!.x - weatherDate!.x - weatherDate!.width).toBeLessThanOrEqual(24)

  if (viewport!.width >= 1024) {
    expect(weatherFacts!.x).toBeGreaterThan(weatherHeading!.x + weatherHeading!.width - 2)
    expect(weatherSummary!.x).toBeGreaterThan(weatherFacts!.x + weatherFacts!.width - 2)
  } else {
    expect(weatherFacts!.y).toBeGreaterThanOrEqual(weatherHeading!.y + weatherHeading!.height)
    expect(weatherSummary!.y).toBeGreaterThanOrEqual(weatherFacts!.y + weatherFacts!.height)
  }

  await expect(page.locator('.candidate-row')).toHaveCount(2)
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  const selectedName = page.locator('.place-detail h2')
  const firstSelectedName = await selectedName.textContent()
  if (viewport!.width <= 600) {
    await expect(page.getByLabel('切换候选地点')).toBeVisible()
    const switcherButtons = page.locator('.candidate-switcher .icon-button')
    await switcherButtons.nth(1).click()
    await expect(selectedName).not.toHaveText(firstSelectedName ?? '')
    await expect(page.locator('.candidate-switcher-current strong')).toHaveText('2/2')
    await switcherButtons.first().click()
    await expect(selectedName).toHaveText(firstSelectedName ?? '')
  } else {
    await page.locator('.candidate-row').nth(1).click()
    await expect(selectedName).not.toHaveText(firstSelectedName ?? '')
    await page.locator('.candidate-row').first().click()
    await expect(selectedName).toHaveText(firstSelectedName ?? '')
  }

  await page.getByRole('button', { name: '修改条件' }).click()
  await expect(page.locator('.travel-form')).toBeVisible()
  await expect(page.getByLabel('切换候选地点')).toHaveCount(0)
  const editingForm = await page.locator('.travel-form').boundingBox()
  const editingContentWidth = await page.evaluate(() => document.documentElement.clientWidth)
  expect(editingForm).not.toBeNull()
  expect(Math.abs(editingForm!.x + editingForm!.width / 2 - editingContentWidth / 2)).toBeLessThanOrEqual(8)

  const dimensions = await page.evaluate(() => ({
    contentWidth: document.documentElement.clientWidth,
    pageWidth: document.documentElement.scrollWidth,
  }))
  expect(dimensions.pageWidth).toBeLessThanOrEqual(dimensions.contentWidth)
})
