import { expect, test, type Page } from '@playwright/test'

let lastCommandAt = 0
async function chat(page: Page, message: string, confirm = false) {
  // Keep this long interaction under the real 10/minute budget, including explanations.
  const wait = Math.max(0, 8000 - (Date.now() - lastCommandAt))
  if (wait) await page.waitForTimeout(wait)
  lastCommandAt = Date.now()
  console.info('chat:', message)
  await page.keyboard.press('Alt+/')
  await expect.poll(() => page.evaluate(() => document.activeElement?.hasAttribute('data-command-input'))).toBe(true)
  const input = page.locator('[data-command-input]:focus')
  await expect(input).toHaveCount(1)
  expect(await input.evaluate(node => !!node.closest('[inert]'))).toBe(false)
  await input.fill(message)
  const planning = page.waitForResponse(r => r.url().endsWith('/assistant/commands/proposals'), { timeout: 15000 })
  const execution = page.waitForResponse(r => r.url().endsWith('/assistant/commands/execute'), { timeout: 15000 })
  await input.press('Enter')
  const proposal = await planning
  expect(proposal.ok(), await proposal.text()).toBeTruthy()
  const plan = await proposal.json()
  expect(plan.question).toBeNull()
  if (confirm) {
    expect(plan.requires_confirmation).toBe(true)
    const reply = page.getByRole('textbox', { name: '确认操作指令' })
    await reply.fill('确认')
    await reply.press('Enter')
  } else expect(plan.requires_confirmation).toBe(false)
  const response = await execution
  expect(response.ok(), await response.text()).toBeTruthy()
  const data = await response.json()
  expect(data.status, JSON.stringify(data)).toBe('completed')
  await expect(page.locator('.studio-composer[data-busy="true"]:visible')).toHaveCount(0)
  return data
}

test('chat drives selection, nested layers, favorites, plans, invitations and history', async ({ page, context }, info) => {
  test.setTimeout(240000)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  const username = 'cmd_' + crypto.randomUUID().replaceAll('-', '').slice(0, 10)
  const registration = await context.request.post('/api/v1/auth/register', {
    data: { username, password: 'isolated-browser-fixture-password' },
  })
  expect(registration.status()).toBe(201)
  const session = await registration.json()
  const chinaDay = new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10)
  const tomorrow = new Date(chinaDay + 'T00:00:00Z')
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1)
  const start = tomorrow.toISOString().slice(0, 10)
  const request = { city: '苏州', main_origin: '苏州站', companion_origins: [], max_distance_km: 500,
    start_date: start, end_date: start, scenery_types: ['lake', 'park', 'museum', 'old_town', 'mountain', 'sea'],
    scenery_match_mode: 'any' }
  const queried = await context.request.post('/api/v1/recommendations', {
    data: request, headers: { 'X-CSRF-Token': session.csrf_token },
  })
  expect(queried.status()).toBe(200)
  const result = await queried.json()
  expect(result.items.length).toBeGreaterThanOrEqual(2)
  await page.addInitScript(({ result, request, start }) => {
    if (sessionStorage.getItem('commands-seeded')) return
    sessionStorage.setItem('commands-seeded', '1')
    sessionStorage.setItem('roambot.studio.session.v1', JSON.stringify({
      version: 2, revision: 0, confirmedFields: ['mainOrigin', 'dates', 'range', 'sceneryTypes'],
      draft: { mode: 'recommendation', city: '', mainOrigin: '苏州站', companions: [],
        mainOriginCoordinate: null, companionOriginCoordinates: [], maxDistance: '500',
        startDate: start, endDate: start, sceneryTypes: request.scenery_types,
        matchMode: 'any', targetPlace: '', destinationRegions: [] },
      result: { version: 1, mode: 'recommendation', items: result.items,
        source_state: result.source_state, generated_at: result.generated_at,
        queryRequest: request, submittedRevision: 0, historyId: result.history_id },
    }))
  }, { result, request, start })
  await page.goto('/recommend')
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await chat(page, '选中前两个')
  await expect(page.getByText('查看对比（2）')).toBeVisible()
  await chat(page, '收藏第二个')
  const favorites = await context.request.get('/api/v1/favorites')
  expect((await favorites.json()).favorites[0].place.provider_place_id).toBe(result.items[1].destination.provider_id)
  await chat(page, '查看第一个地点')
  await expect(page.locator('[data-detail-id]:not([data-exit-snapshot])')).toBeVisible()
  await chat(page, '查看位置')
  await expect(page.locator('.location-backdrop:not([data-exit-snapshot])')).toBeVisible()
  await chat(page, '返回')
  await expect(page.locator('.location-backdrop:not([data-exit-snapshot])')).toHaveCount(0)
  await expect(page.locator('[data-detail-id]:not([data-exit-snapshot])')).toBeVisible()
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await chat(page, '返回')
  await expect(page.locator('[data-detail-id]:not([data-exit-snapshot])')).toHaveCount(0)
  await chat(page, '查看对比')
  await expect(page.getByRole('dialog', { name: '候选对比' })).toBeVisible()
  await chat(page, '返回')
  await expect(page.getByRole('dialog', { name: '候选对比' })).toHaveCount(0)
  await chat(page, '就这两个，建个计划')
  await expect(page).toHaveURL(/\/plans\/[^/]+$/)
  await chat(page, '把计划改名为周末出游')
  await expect(page.getByRole('heading', { name: '周末出游' })).toBeVisible()
  await chat(page, '生成邀请', true)
  await expect(page.getByRole('link', { name: '打开刚生成的链接' })).toHaveAttribute('href', /^\/join\//)
  const plans = (await (await context.request.get('/api/v1/plans')).json()).plans
  expect(plans).toHaveLength(1)
  expect(plans[0].name).toBe('周末出游')
  await page.screenshot({ path: info.outputPath('chat-plan.png'), fullPage: true })
  await chat(page, '查看历史')
  await expect(page).toHaveURL(/\/history$/)
  await chat(page, '分享第一条历史')
  await expect(page.getByRole('link', { name: '打开刚生成的链接' })).toHaveAttribute('href', /^\/share\//)
  await chat(page, '查看收藏')
  await expect(page).toHaveURL(/\/favorites$/)
  await chat(page, '查看第一个地点')
  await expect(page.getByRole('dialog')).toBeVisible()
  await chat(page, '返回')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(errors).toEqual([])
})
