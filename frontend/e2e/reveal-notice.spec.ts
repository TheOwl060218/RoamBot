import { expect, test } from '@playwright/test'
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

test('second candidate announces offscreen comparison without repeating for a third or visible comparison', async ({ page }, info) => {
  const plan = workbenchPlan()
  const response = { items: plan.candidates.map(candidate => ({ ...candidate.snapshot,
    destination: { ...candidate.snapshot.destination, provider_id: candidate.id, coordinate: { longitude: 120.6, latitude: 31.3, system: 'gcj02' }, type_name: '景点', type_code: '110000', popularity_rank: null },
    distances: [{ origin_label: '苏州站', distance_km: 2, duration_minutes: 10, estimated: true }],
  })), generated_at: '2026-10-07T00:00:00Z', source_state: { kind: 'demo', notices: [] }, uncovered_scenery_types: [] }
  await page.addInitScript(data => sessionStorage.setItem('roambot.session.search-result.v1', JSON.stringify(data)), response)
  await page.route('**/api/v1/**', route => route.fulfill({ json: { user: null } }))
  await page.setViewportSize({ width: page.viewportSize()!.width, height: 650 })
  await page.goto('/recommend')
  const choices = page.getByRole('group', { name: '选择候选进行对比' }).getByRole('checkbox')
  const bubble = page.getByRole('status').filter({ hasText: '对比已准备好' })
  await choices.nth(0).check()
  await expect(bubble).toHaveCount(0)
  await choices.nth(1).check()
  await expect(bubble).toBeVisible()
  await page.screenshot({ path: info.outputPath('comparison-notice.png') })
  await expect(bubble).toHaveCount(0, { timeout: 3500 })
  await choices.nth(2).check()
  await page.waitForTimeout(100)
  await expect(bubble).toHaveCount(0)
  await choices.nth(2).uncheck()
  await choices.nth(1).uncheck()
  // A tall viewport exposes the right-hand comparison without auto-scrolling it.
  await page.setViewportSize({ width: page.viewportSize()!.width, height: 3000 })
  await choices.nth(1).check()
  await page.waitForTimeout(100)
  await expect(bubble).toHaveCount(0)
})
