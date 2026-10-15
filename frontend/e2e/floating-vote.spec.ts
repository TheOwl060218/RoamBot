import { expect, test } from '@playwright/test'

test('participant can inspect weather while voting and keeps an unsubmitted draft', async ({ page }, info) => {
  const weather = Array.from({ length: 6 }, (_, i) => ({ date: `2026-12-0${i + 1}`, condition: i % 2 ? '小雨' : '多云', temp_min_c: 20, temp_max_c: 26 }))
  const snapshot = { destination: { name: '苏州博物馆', address: '苏州', rating: null }, score: { total: 90, weather: 85, distance: 90 },
    group_accessibility: { average_distance_km: 2, max_distance_km: 3, fairness_score: 100 }, weather,
    daily_suitability: weather.map(day => ({ date: day.date, status: 'suitable', summary: '注意携带雨具。' })), overall_advice: 'suitable', explanation: '不应显示的推荐理由' }
  let plan = { id: 'vote-fixture', name: '浮动投票演示', city: '苏州', start_date: '2026-12-01', end_date: '2026-12-06', status: 'voting', ended: false,
    final_candidate_id: null, expected_count: 2, summary: null, participants: null,
    me: { id: 'guest', nickname: '同行甲', preferred_id: '', acceptable_ids: [] as string[] },
    candidates: [{ id: 'a', snapshot }, { id: 'b', snapshot: { ...snapshot, destination: { ...snapshot.destination, name: '金鸡湖' } } }] }
  let votes = 0
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/vote')) {
      votes++
      expect(route.request().method()).toBe('PUT')
      expect(route.request().postDataJSON()).toEqual({ preferred_id: 'b', acceptable_ids: [] })
      expect(route.request().headers()['x-plan-csrf']).toBe('fixture')
      plan = { ...plan, me: { ...plan.me, preferred_id: 'b' } }
    }
    await route.fulfill({ json: path.endsWith('/auth/me') ? { user: null } : { plan, anonymous_csrf: 'fixture' } })
  })
  await page.goto('/join/fixture')
  await page.getByRole('button', { name: '查看苏州博物馆详情' }).click()
  await expect(page.locator('.weather-condition svg').first()).toBeVisible()
  await expect(page.getByText('不应显示的推荐理由')).toHaveCount(0)
  await page.getByRole('button', { name: '去投票' }).click()
  const panel = page.getByRole('dialog', { name: '我的投票' })
  await expect.poll(async () => {
    const bounds = await panel.boundingBox()
    const viewport = page.viewportSize()!
    return Boolean(bounds && bounds.x + bounds.width <= viewport.width && bounds.y + bounds.height < viewport.height)
  }).toBe(true)
  const bounds = (await panel.boundingBox())!
  const viewport = page.viewportSize()!
  expect(bounds.x).toBeGreaterThanOrEqual(0)
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(viewport.width)
  expect(bounds.y).toBeGreaterThanOrEqual(100)
  expect(bounds.y + bounds.height).toBeLessThan(viewport.height)
  await page.getByRole('radio', { name: '首选 金鸡湖' }).check()
  await page.screenshot({ path: info.outputPath('floating-vote-preview.png') })
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  // Compact layouts need not overflow vertically; voting stays usable if they do.
  const expectedScroll = await page.evaluate(() => Math.max(0, document.documentElement.scrollHeight - innerHeight))
  expect(await page.evaluate(() => window.scrollY)).toBeCloseTo(expectedScroll, 0)
  await expect(panel).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(panel).toBeHidden()
  expect(votes).toBe(0)
  await page.getByRole('button', { name: '继续投票' }).click()
  await expect(page.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
  await page.getByRole('button', { name: '提交投票', exact: true }).click()
  await expect(panel).toBeHidden()
  await page.getByRole('button', { name: '修改投票', exact: true }).click()
  await expect(page.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
  plan = { ...plan, status: 'closed' }
  await page.reload()
  await expect(page.getByText(/等待发起者决定目的地/)).toBeVisible()
  await expect(page.getByRole('radio')).toHaveCount(0)
  await expect(page.locator('.plan-vote-float')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})
