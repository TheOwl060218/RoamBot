import { expect, test } from '@playwright/test'

test('plan detail compares one day with final destination first and optional management', async ({ page }) => {
  const snapshot = { destination: { name: '苏州博物馆', address: '苏州', city: '苏州' },
    score: { total: 90, weather: 85, distance: 90, fairness: 100 }, group_accessibility: { average_distance_km: 2, max_distance_km: 3, fairness_score: 100 },
    overall_advice: 'suitable', daily_suitability: Array.from({ length: 6 }, (_, i) => ({ date: `2026-12-0${i + 1}`, score: 85, status: 'suitable', summary: '天气总体适合出行。', reasons: [] })), explanation: '旧推荐理由', weather: Array.from({ length: 6 }, (_, i) => ({ date: `2026-12-0${i + 1}`, condition: '多云', temp_min_c: 20, temp_max_c: 26 })) }
  const plan = { id: 'layout-fixture', name: '苏州出行计划', city: '苏州', start_date: '2026-12-01', end_date: '2026-12-06',
    status: 'decided', ended: false, final_candidate_id: 'b', expected_count: 2,
    candidates: [{ id: 'a', snapshot }, { id: 'b', snapshot: { ...snapshot, destination: { ...snapshot.destination, name: '金鸡湖' } } }],
    participants: [{ id: 'owner', nickname: '演示用户', role: 'owner', voted: true }], summary: null, invite_active: false }
  // All API requests are fixtures: the running user's database is never accessed.
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    const json = path.endsWith('/auth/me') ? { user: { username: 'fixture' }, csrf_token: 'fixture' }
      : path.endsWith('/plans') ? { plans: [] }
      : path.endsWith('/invite/rotate') ? { url: '/join/fixture' } : { plan }
    return route.fulfill({ json })
  })
  await page.goto('/plans/layout-fixture')
  await expect(page.getByRole('heading', { name: plan.name, exact: true })).toBeVisible()
  const cards = page.locator('article.plan-comparison-card')
  await expect(cards.first().getByRole('heading', { name: '金鸡湖' })).toBeVisible()
  await expect(cards.first().getByRole('button', { name: '查看金鸡湖详情' })).toHaveAttribute('aria-expanded', 'false')
  await expect(cards.nth(1).locator('.weather-condition svg')).toHaveCount(1)
  await page.getByRole('button', { name: '查看苏州博物馆详情' }).click()
  await expect(cards.nth(1).getByText(/创建时保存的天气/)).toBeVisible()
  await expect(cards.nth(1).locator('.weather-condition svg')).toHaveCount(1)
  await expect(cards.nth(1).getByText('旧推荐理由')).toHaveCount(0)
  await page.getByRole('button', { name: '收起苏州博物馆详情' }).click()
  await page.getByRole('button', { name: '管理计划', exact: true }).click()
  await page.getByRole('button', { name: '编辑计划信息' }).click()
  await expect(page.getByLabel('计划名称')).toHaveValue(plan.name)
  await page.getByRole('button', { name: '收起计划编辑' }).click()
  await page.getByRole('button', { name: '生成邀请', exact: true }).click()
  const feedback = page.getByRole('status').filter({ hasText: '邀请已生成' })
  await expect(feedback).toBeVisible()
  const bubble = (await feedback.boundingBox())!
  const header = (await page.locator('.shell-header').boundingBox())!
  expect(bubble.y).toBeGreaterThanOrEqual(header.y + header.height)
  expect(bubble.x).toBeGreaterThanOrEqual(0)
  expect(bubble.x + bubble.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  await expect(feedback).toHaveCount(0, { timeout: 4000 })
  await expect(page.getByLabel('邀请链接')).toBeVisible()
  const management = (await page.getByRole('region', { name: '计划管理' }).boundingBox())!
  const card = (await cards.first().boundingBox())!
  expect(card.y).toBeGreaterThan(management.y + management.height)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})
