import { expect, test } from '@playwright/test'
import { fillStudioConditions } from './helpers'
import { workbenchPlan } from '../tests/fixtures/workbenchPlan'

test('all dates announces offscreen content, expires, and stays quiet when the table is visible', async ({ page }, info) => {
  const plan = workbenchPlan()
  await page.route('**/api/v1/**', route => route.fulfill({ json: new URL(route.request().url()).pathname.endsWith('/auth/me') ? { user: null } : { plan, anonymous_csrf: 'fixture' } }))
  await page.setViewportSize({ width: page.viewportSize()!.width, height: 600 })
  await page.goto('/join/fixture')
  await page.getByRole('button', { name: '查看全部日期', exact: true }).click()
  const bubble = page.getByRole('status').filter({ hasText: '全部日期已展开' })
  await expect(bubble).toBeVisible()
  const box = (await bubble.boundingBox())!
  expect(box.x).toBeGreaterThanOrEqual(0)
  expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  await page.screenshot({ path: info.outputPath('all-dates-notice.png') })
  await expect(bubble).toHaveCount(0, { timeout: 3500 })
  await page.getByRole('button', { name: '收起全部日期', exact: true }).click()
  await page.setViewportSize({ width: page.viewportSize()!.width, height: 2200 })
  await page.getByRole('button', { name: '查看全部日期', exact: true }).click()
  await page.waitForTimeout(100)
  await expect(bubble).toHaveCount(0)
  await expect(page.getByRole('table', { name: '全部日期天气对比' })).toBeVisible()
})

test('candidate dock presents comparison affordance without repeated toast noise', async ({ page }) => {
  await page.goto('/recommend')
  await fillStudioConditions(page, ['湖景','博物馆','古镇/历史街区'])
  await page.getByRole('button', { name: '开始推荐' }).click()
  await page.getByRole('button', { name: /^加入候选：/ }).first().click()
  await expect(page.getByRole('button', { name: '查看对比（1）' })).toBeDisabled()
  await page.getByRole('button', { name: /^加入候选：/ }).first().click()
  await expect(page.getByRole('button', { name: '查看对比（2）' })).toBeEnabled()
  await page.getByRole('button', { name: /^加入候选：/ }).first().click()
  await expect(page.getByRole('button', { name: '查看对比（3）' })).toBeEnabled()
  await expect(page.getByRole('status').filter({ hasText: '对比已准备好' })).toHaveCount(0)
  await page.getByRole('button', { name: '查看对比（3）' }).click()
  await expect(page.getByRole('region', { name: '候选对比' }).locator('article')).toHaveCount(3)
})
