import { expect, test } from '@playwright/test'

import { tomorrowInChina } from './helpers'

test('candidate comparison can be used and stays horizontal-safe', async ({ page }) => {
  await page.goto('/')

  const date = tomorrowInChina()
  await page.getByLabel('主出发地', { exact: true }).fill('苏州站')
  await page.getByLabel('最大距离（km）', { exact: true }).fill('80')
  await page.getByLabel('开始日期', { exact: true }).fill(date)
  await page.getByLabel('结束日期', { exact: true }).fill(date)
  await page.getByRole('checkbox', { name: '湖景', exact: true }).check()
  await page.getByRole('checkbox', { name: '古镇/历史街区', exact: true }).check()
  await page.getByRole('checkbox', { name: '博物馆', exact: true }).check()
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  await expect(page.locator('.place-detail')).toBeVisible()
  await expect(page.getByRole('button', { name: '重新查询', exact: true })).toBeVisible()

  const group = page.getByRole('group', { name: '选择候选进行对比' })
  await expect(group).toBeVisible()

  const checkboxes = group.getByRole('checkbox')
  await expect(checkboxes).toHaveCount(3)

  await checkboxes.nth(0).check()
  await expect(page.getByRole('table', { name: '候选地点对比' })).toHaveCount(0)

  await checkboxes.nth(1).check()
  const table = page.getByRole('table', { name: '候选地点对比' })
  await expect(table).toBeVisible()
  await expect(page.locator('.comparison-conclusion').first()).toBeVisible()
  await expect(page.getByText('最佳').first()).toBeVisible()
  await expect(page.locator('.candidate-comparison-table th[scope="col"]').first()).toBeVisible()
  await expect(page.locator('.candidate-comparison-table th[scope="row"]').first()).toBeVisible()

  await page.getByRole('button', { name: '查看对比结果（2）' }).click()
  const comparisonTarget = page.locator('.comparison-focus-target')
  await expect(comparisonTarget).toBeFocused()
  await expect(comparisonTarget).toHaveClass(/comparison-focus-highlight/)

  if (page.viewportSize()!.width <= 600) {
    const scrollable = page.locator('.comparison-table-scroll')
    await scrollable.evaluate((element) => {
      element.scrollLeft = element.scrollWidth
    })
    expect(await scrollable.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0)
  }

  await checkboxes.nth(1).uncheck()
  await expect(page.getByRole('table', { name: '候选地点对比' })).toHaveCount(0)

  const dimensions = await page.evaluate(() => ({
    contentWidth: document.documentElement.clientWidth,
    pageWidth: document.documentElement.scrollWidth,
  }))
  expect(dimensions.pageWidth).toBeLessThanOrEqual(dimensions.contentWidth)
})
