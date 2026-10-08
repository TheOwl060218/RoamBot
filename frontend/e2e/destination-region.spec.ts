import { expect, test, type Page } from '@playwright/test'
import { registerUser, tomorrowInChina } from './helpers'

test('form rows have consistent spacing without blank error placeholders', async ({ page }, testInfo) => {
  await page.goto('/recommend')
  const city = page.locator('.form-city-field')
  const origins = page.locator('.form-origins-field')
  const distance = page.getByLabel('最大距离（km）').locator('..')
  const regions = page.getByRole('combobox', { name: '目的地城市范围' }).locator('../../..')
  const date = page.getByLabel('开始日期').locator('..')
  const gap = async (first: typeof city, second: typeof city) => {
    const a = (await first.boundingBox())!, b = (await second.boundingBox())!
    return b.y - a.y - a.height
  }
  expect(await gap(city, origins)).toBeCloseTo(24, 0)
  expect(await gap(origins, distance)).toBeCloseTo(24, 0)
  expect(await gap(testInfo.project.name === 'desktop-chromium' ? distance : regions, date)).toBeCloseTo(24, 0)
  await expect(city.locator('.field-message')).toHaveCSS('display', 'none')
  const origin = page.getByLabel('主出发地', { exact: true })
  const originBox = (await origin.boundingBox())!
  const addBox = (await page.getByRole('button', { name: '添加同行人' }).boundingBox())!
  expect(addBox.y - originBox.y - originBox.height).toBeCloseTo(12, 0)
  await page.screenshot({ path: `../evidence/form-spacing-${testInfo.project.name}-20261008.png`, fullPage: true })
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  await expect(origins.locator('.field-error').filter({ hasText: '请输入主出发地' })).toBeVisible()
  await origin.fill('苏州站')
  const suggestions = page.getByRole('listbox', { name: '主出发地候选项' })
  await expect(suggestions).toBeVisible()
  const inputBox = (await origin.boundingBox())!, suggestionsBox = (await suggestions.boundingBox())!
  expect(suggestionsBox.y).toBeGreaterThanOrEqual(inputBox.y + inputBox.height)
})

test('region reset is an outlined button and keeps the distance limit', async ({ page }, testInfo) => {
  await page.goto('/recommend')
  await page.getByLabel('最大距离（km）').fill('125')
  await selectRegion(page, '杭', '杭州市 · 浙江省')
  await page.getByRole('button', { name: '选择省市', exact: true }).click()
  const reset = page.getByRole('button', { name: '恢复不限', exact: true })
  await expect(reset).toHaveCSS('border-top-style', 'solid')
  await expect(reset).toHaveCSS('border-radius', '999px')
  expect((await reset.boundingBox())!.height).toBeGreaterThanOrEqual(44)
  const information = page.getByText(/目录覆盖大陆31个省级地区/)
  await expect(information).not.toBeVisible()
  await page.getByText('地区信息', { exact: true }).click()
  await expect(information).toBeVisible()
  await page.getByText('地区信息', { exact: true }).click()
  await reset.click()
  await page.getByRole('button', { name: '完成选择', exact: true }).click()
  const input = page.getByRole('combobox', { name: '目的地城市范围' })
  await expect(input).toHaveAttribute('placeholder', '距离内不限省市')
  await expect(page.getByLabel('最大距离（km）')).toHaveValue('125')
  await selectRegion(page, '北京', '北京市')
  await input.press('Backspace')
  await expect(input).toHaveAttribute('placeholder', '距离内不限省市')
  await selectRegion(page, '北京', '北京市')
  await input.press('Delete')
  await expect(input).toHaveAttribute('placeholder', '距离内不限省市')
  await page.getByRole('button', { name: '选择省市', exact: true }).click()
  await page.screenshot({ path: `../evidence/region-controls-${testInfo.project.name}-20261008.png`, fullPage: true })
})

test('departure fields precede limits with balanced desktop columns and no mobile overflow', async ({ page }, testInfo) => {
  await page.goto('/recommend')
  const city = page.getByLabel('出发城市', { exact: true })
  const origins = page.getByRole('group', { name: '从哪里出发' })
  const distance = page.getByLabel('最大距离（km）')
  const regions = page.getByRole('combobox', { name: '目的地城市范围' })
  await expect(city).toBeVisible()
  const cityBox = (await city.boundingBox())!
  const originsBox = (await origins.boundingBox())!
  const distanceBox = (await distance.boundingBox())!
  const regionBox = (await regions.locator('..').boundingBox())!
  expect(originsBox.y).toBeGreaterThan(cityBox.y + cityBox.height)
  expect(distanceBox.y).toBeGreaterThan(originsBox.y + originsBox.height)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: `../evidence/search-layout-${testInfo.project.name}-20261008.png`, fullPage: true })
  if (testInfo.project.name === 'desktop-chromium') {
    const layout = (await page.locator('.workspace-layout').boundingBox())!
    const sidebar = (await page.locator('.workspace-sidebar').boundingBox())!
    expect(sidebar.width / layout.width).toBeGreaterThan(0.35)
    expect(sidebar.width / layout.width).toBeLessThan(0.37)
    expect(Math.abs(distanceBox.y - regionBox.y)).toBeLessThan(2)
    const resizer = (await page.getByRole('separator', { name: '调整侧栏宽度' }).boundingBox())!
    await page.mouse.move(resizer.x + 5, resizer.y + 10)
    await page.mouse.down()
    await page.mouse.move(resizer.x + 85, resizer.y + 10)
    await page.mouse.up()
    expect((await page.locator('.workspace-sidebar').boundingBox())!.width).toBeGreaterThan(sidebar.width + 60)
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('region popup does not shift preferences and has one focus frame', async ({ page }, testInfo) => {
  await page.goto('/recommend')
  const input = page.getByRole('combobox', { name: '目的地城市范围' })
  await expect(input).toBeVisible()
  const scenery = page.locator('.choice-grid')
  const before = await scenery.boundingBox()
  const button = page.getByRole('button', { name: '选择省市', exact: true })
  const target = await button.boundingBox()
  expect(target!.width).toBeGreaterThanOrEqual(44)
  expect(target!.height).toBeGreaterThanOrEqual(44)
  await input.fill('杭')
  await expect(page.getByRole('option', { name: /杭州市/ })).toBeVisible()
  await expect(input).toHaveCSS('outline-width', '0px')
  await expect(input).toHaveCSS('box-shadow', 'none')
  expect(Math.abs((await scenery.boundingBox())!.y - before!.y)).toBeLessThanOrEqual(1)
  await page.getByRole('option', { name: /杭州市/ }).click()
  expect(Math.abs((await scenery.boundingBox())!.y - before!.y)).toBeLessThanOrEqual(1)
  await input.press('Escape')
  await page.screenshot({ path: `../evidence/destination-regions-${testInfo.project.name}-20261008.png`, fullPage: true })
  await page.setViewportSize({ width: 320, height: 844 })
  await button.click()
  const panel = await page.getByRole('dialog', { name: '选择省市' }).boundingBox()
  expect(panel!.x).toBeGreaterThanOrEqual(0)
  expect(panel!.x + panel!.width).toBeLessThanOrEqual(320)
})

async function selectRegion(page: Page, text: string, option: string) {
  await page.getByRole('combobox', { name: '目的地城市范围' }).fill(text)
  await page.getByRole('option', { name: option, exact: true }).click()
}

async function recommendRegions(page: Page) {
  await page.getByLabel('主出发地', { exact: true }).fill('苏州站')
  await page.getByLabel('最大距离（km）').fill('200')
  await page.getByLabel('开始日期').fill(tomorrowInChina())
  await page.getByLabel('结束日期').fill(tomorrowInChina())
  await page.getByRole('checkbox', { name: '湖景', exact: true }).check()
  const response = page.waitForResponse((r) => r.url().endsWith('/recommendations') && r.request().method() === 'POST')
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  const received = await response
  expect(received.status()).toBe(200)
  return { payload: received.request().postDataJSON(), result: await received.json() }
}

test('guest multi-region request excludes other provinces and summary ignores later edits', async ({ page }) => {
  await page.goto('/recommend')
  await selectRegion(page, '江苏', '江苏省')
  await selectRegion(page, '杭', '杭州市 · 浙江省')
  const { payload, result } = await recommendRegions(page)
  expect(payload.destination_regions).toEqual(['320000', '330100'])
  expect(new Set(result.items.map((item: { destination: { city_adcode: string } }) => item.destination.city_adcode)))
    .toEqual(new Set(['320500', '330100']))
  for (const item of result.items) expect(item.distances[0].distance_km).toBeLessThanOrEqual(200)
  expect(result.history_id ?? null).toBeNull()
  const summary = page.getByRole('region', { name: '当前查询条件' })
  await expect(summary).toContainText('江苏省、杭州市')
  await page.getByRole('button', { name: '重新查询', exact: true }).click()
  await page.getByRole('button', { name: '选择省市', exact: true }).click()
  await page.getByRole('button', { name: '恢复不限', exact: true }).click()
  await page.getByRole('button', { name: '完成选择', exact: true }).click()
  await expect(summary).toContainText('江苏省、杭州市')
})

test('account history rerun preserves selected destination scope', async ({ page }, testInfo) => {
  await page.goto('/recommend')
  await registerUser(page, `regions_${testInfo.project.name}`)
  await selectRegion(page, '杭', '杭州市 · 浙江省')
  const { result } = await recommendRegions(page)
  expect(result.history_id).toBeTruthy()
  await page.goto('/history')
  await page.getByRole('button', { name: '更多历史操作', exact: true }).first().click()
  const response = page.waitForResponse((r) => r.url().endsWith('/rerun') && r.request().method() === 'POST')
  await page.getByRole('button', { name: '重新查询', exact: true }).click()
  expect((await response).status()).toBe(200)
  await expect(page).toHaveURL(/\/recommend$/)
  await expect(page.getByRole('region', { name: '当前查询条件' })).toContainText('杭州市')
  await page.getByRole('button', { name: '重新查询', exact: true }).click()
  await expect(page.getByRole('button', { name: /移除杭州市|查看全部已选地区/ })).toBeVisible()
})
