import { test, expect } from '@playwright/test'
import { fillStudioConditions, registerUser, tomorrowInChina } from './helpers'

test.use({ video: 'on' })
for (const width of [1440, 1280, 390, 320]) for (const reduced of [false, true]) {
  test(`${width}px ${reduced ? 'reduced' : 'normal'} spatial flow`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width > 600 ? 900 : 844 })
    await page.emulateMedia({ reducedMotion: reduced ? 'reduce' : 'no-preference' })
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    // Layout matrix uses a controlled transport; the stage test exercises the
    // real Mock API separately without exhausting its per-IP safety limiter.
    await page.route('**/api/v1/assistant/turns', route => {
      const body = route.request().postDataJSON()
      return route.fulfill({ json: { revision: body.revision, source: 'demo', reply: '条件已更新。', patch: {
        main_origin: '苏州站', start_date: tomorrowInChina(), end_date: tomorrowInChina(), max_distance_km: 80,
        scenery_types: ['lake', 'museum', 'park'], scenery_query: body.message, scenery_keywords: [],
      } } })
    })
    await page.goto('/recommend')
    await registerUser(page, `s${width}`)
    await expect(page.locator('.condition-piece')).toHaveCount(0)
    await page.screenshot({ path: testInfo.outputPath('initial.png') })
    await page.getByRole('button', { name: '更多功能', exact: true }).click()
    await expect(page.getByRole('dialog', { name: '更多功能' })).toBeVisible()
    await page.locator('.studio-overlay-backdrop').click({ position: { x: 3, y: 3 } })
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await fillStudioConditions(page, ['湖景', '博物馆', '公园'])
    await expect(page.locator('.studio-query-page .condition-piece')).toHaveCount(4)
    await page.getByRole('button', { name: /编辑日期/ }).click()
    await page.getByRole('button', { name: '明天', exact: true }).click()
    await expect(page.locator('input[type=date]')).toHaveCount(0)
    await page.getByRole('button', { name: '保存条件' }).click()
    await page.getByRole('button', { name: /编辑想找的地方/ }).click()
    await expect(page.getByRole('checkbox')).toHaveCount(0)
    await page.getByLabel('想找什么样的地方').fill('湖边、博物馆、公园')
    await page.getByRole('button', { name: '保存条件' }).click()
    await expect(page.getByRole('button', { name: '开始推荐', exact: true })).toBeEnabled()
    await page.screenshot({ path: testInfo.outputPath('conditions.png') })
    await page.route('**/api/v1/recommendations', async route => {
      const response = await route.fetch()
      await new Promise(resolve => setTimeout(resolve, 700))
      await route.fulfill({ response })
    })
    await page.getByRole('button', { name: '开始推荐', exact: true }).click()
    await expect(page.getByText('已开始推荐 · 正在结合天气、距离和你的偏好', { exact: true })).toBeVisible()
    if (!reduced) {
      await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'toResults')
      await page.waitForTimeout(350)
      await page.screenshot({ path: testInfo.outputPath('enter-mid.png') })
    }
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await expect(page.getByTestId('destination-card').first()).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('results.png') })
    await page.getByRole('button', { name: /^了解/ }).first().click()
    await expect(page.getByRole('dialog', { name: /详情$/ })).toBeVisible()
    expect(await page.locator('.destination-detail').evaluate(el => {
      const color = getComputedStyle(el).backgroundColor
      return color.startsWith('rgba(') ? Number(color.split(',').at(-1)?.replace(')', '')) : color !== 'transparent'
    })).toBeGreaterThan(.7)
    await page.waitForTimeout(reduced ? 20 : 600)
    await page.screenshot({ path: testInfo.outputPath('detail.png') })
    await page.locator('.destination-detail-layer').click({ position: { x: 3, y: 3 } })
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await page.getByRole('button', { name: '↻ 新查询' }).click()
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'query')
    await expect(page.locator('.studio-query-page .condition-piece')).toHaveCount(0)
    await page.getByRole('button', { name: '撤销', exact: true }).click()
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await expect(page.locator('.studio-dirty')).toHaveCount(0)
    await page.getByRole('button', { name: '← 返回修改' }).click()
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'query')
    await page.getByRole('button', { name: /编辑日期/ }).click()
    await page.keyboard.press('Escape')
    await page.getByRole('button', { name: '移除日期' }).click()
    await expect(page.getByRole('button', { name: /编辑日期/ })).toHaveCount(0)
    await page.screenshot({ path: testInfo.outputPath('returned.png') })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(errors).toEqual([])
  })
}
