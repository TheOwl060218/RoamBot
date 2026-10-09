import { expect, test } from '@playwright/test'
import { tomorrowInChina } from './helpers'

test('two region names truncate naturally, extras are counted, and deletion remains usable', async ({ page }, info) => {
  await page.goto('/recommend')
  const input = page.getByRole('combobox', { name: '目的地城市范围' })
  for (const [query, option] of [['上海', '上海市'], ['乌鲁木齐', '乌鲁木齐市 · 新疆维吾尔自治区'], ['吐鲁番', '吐鲁番市 · 新疆维吾尔自治区']]) {
    await input.fill(query)
    await page.getByRole('option', { name: option, exact: true }).click()
  }
  await expect(page.getByRole('button', { name: '移除上海市', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '移除乌鲁木齐市', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '查看全部已选地区' })).toHaveText('+1')
  await expect(input).toHaveAttribute('placeholder', '')
  await expect(page.locator('.region-control .region-chip[title] span').first()).toHaveCSS('text-overflow', 'ellipsis')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  const control = page.locator('.region-control')
  expect(await control.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
  const secondName = page.getByRole('button', { name: '移除乌鲁木齐市', exact: true }).locator('span').first()
  expect(await secondName.evaluate(el => el.clientWidth)).toBeGreaterThanOrEqual(30)
  await page.screenshot({ path: `../evidence/region-two-names-${info.project.name}-20261009.png` })
  await input.press('Backspace')
  await expect(page.getByRole('button', { name: '查看全部已选地区' })).toHaveCount(0)
  await input.fill('杭')
  await input.press('Backspace')
  await expect(page.getByRole('button', { name: '移除乌鲁木齐市', exact: true })).toBeVisible()
})

test('multi-day query retains daily rows but has no generic repeated reminder', async ({ page }, info) => {
  await page.goto('/recommend')
  await page.getByLabel('主出发地', { exact: true }).fill('苏州站')
  const start = tomorrowInChina()
  const end = new Date(`${start}T00:00:00Z`)
  end.setUTCDate(end.getUTCDate() + 2)
  await page.getByLabel('开始日期', { exact: true }).fill(start)
  await page.getByLabel('结束日期', { exact: true }).fill(end.toISOString().slice(0, 10))
  await page.getByRole('checkbox', { name: '湖景', exact: true }).check()
  const response = page.waitForResponse('**/api/v1/recommendations')
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  const apiResponse = await response
  expect(apiResponse.status()).toBe(200)
  expect(apiResponse.request().postDataJSON().city).toBe('')
  await expect(page.locator('.place-detail .weather-day')).toHaveCount(3)
  await expect(page.locator('.place-detail')).not.toContainText('无特别提醒')
  await expect(page.locator('.place-detail')).not.toContainText('天气条件总体较适合出行')
  await page.locator('.place-detail').scrollIntoViewIfNeeded()
  await page.screenshot({ path: `../evidence/weather-reminders-${info.project.name}-20261009.png`, fullPage: true })
})
