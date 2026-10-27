import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { workbenchPlan } from '../tests/fixtures/workbenchPlan'

const preserved = JSON.parse(readFileSync(new URL('./fixtures/discovery-preserved.json', import.meta.url), 'utf8'))

test('preserved real place facts stay compact, submitting does not shift the dock, and buttons bypass chat', async ({ page }, testInfo) => {
  let jobs = 0, assistantRequests = 0
  const plans: Record<string, unknown>[] = []
  await page.route('**/api/v1/**', async route => {
    const r = route.request(), path = new URL(r.url()).pathname
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { user: { username: 'layout_owner' }, csrf_token: 'isolated-csrf' } })
    if (path.includes('/assistant/')) { assistantRequests++; return route.fulfill({ status: 500, json: {} }) }
    if (path === '/api/v1/discovery/jobs' && r.method() === 'POST') return route.fulfill({ json: { id: 'preserved-' + (++jobs) } })
    if (path.endsWith('/history')) return route.fulfill({ json: { history_id: 'owned-history' } })
    if (path.startsWith('/api/v1/discovery/jobs/')) return route.fulfill({ json: { ...preserved, id: 'preserved-' + jobs } })
    if (path === '/api/v1/plans' && r.method() === 'POST') { plans.push(r.postDataJSON()); return route.fulfill({ json: { plan: { id: 'direct-plan' } } }) }
    if (path === '/api/v1/plans') return route.fulfill({ json: { plans: [] } })
    if (path === '/api/v1/plans/direct-plan') return route.fulfill({ json: { plan: { ...workbenchPlan(), id: 'direct-plan' } } })
    return route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'not configured' } } })
  })
  await page.goto('/explore')
  const idea = '杭州赏秋，想在户外轻松走走，不去商场'
  const input = page.getByRole('textbox', { name: '继续补充条件' })
  await input.fill(idea); await input.press('Enter')
  const cards = page.locator('.discovery-card')
  await expect(cards).toHaveCount(10)
  await page.locator('.route-content').evaluate(async node => {
    await Promise.all(node.getAnimations({ subtree: true }).filter(a => a.effect?.getComputedTiming().iterations !== Infinity).map(a => a.finished.catch(() => undefined)))
  })
  const first = cards.first()
  const measurements = await cards.evaluateAll(nodes => nodes.map(n => ({ height: n.getBoundingClientRect().height,
    footerBottom: n.querySelector('footer')!.getBoundingClientRect().bottom, bottom: n.getBoundingClientRect().bottom })))
  expect(measurements.every(n => n.height <= 335 && n.footerBottom <= n.bottom)).toBe(true)
  const y = (await first.boundingBox())!.y, dock = (await page.locator('.discovery-input').boundingBox())!
  await input.fill(idea); await input.press('Enter')
  await expect.poll(() => jobs).toBe(2)
  await expect(page.getByRole('button', { name: '停止查找' })).toHaveCount(0)
  expect(Math.abs((await first.boundingBox())!.y - y)).toBeLessThan(2)
  expect(Math.abs((await page.locator('.discovery-input').boundingBox())!.y - dock.y)).toBeLessThan(2)
  await first.getByRole('button', { name: '加入比较', exact: true }).click()
  await cards.nth(1).getByRole('button', { name: '加入比较', exact: true }).click()
  const selection = page.locator('.discovery-selection')
  await selection.scrollIntoViewIfNeeded()
  expect((await selection.boundingBox())!.y + (await selection.boundingBox())!.height).toBeLessThan((await page.locator('.discovery-input').boundingBox())!.y)
  await page.screenshot({ path: testInfo.outputPath('preserved-results.png') })
  await page.getByRole('button', { name: '查看对比', exact: true }).click()
  const compare = page.getByRole('dialog', { name: '地点对比' })
  await expect(compare.getByRole('rowheader', { name: '开放时间' })).toBeVisible()
  await compare.evaluate(async node => { await Promise.all(node.parentElement!.getAnimations({ subtree: true }).map(a => a.finished.catch(() => undefined))) })
  await page.screenshot({ path: testInfo.outputPath('comparison-table.png') })
  await compare.getByRole('button', { name: '返回推荐' }).click()
  await page.getByRole('button', { name: '发起同行计划', exact: true }).click()
  const form = page.getByRole('dialog', { name: '创建同行计划' })
  await expect(form).toBeVisible()
  expect(assistantRequests).toBe(0); expect(jobs).toBe(2); expect(plans).toHaveLength(0)
  const date = new Date(); date.setDate(date.getDate() + 1)
  const text = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  await form.getByLabel('出发日期').fill(text); await form.getByLabel('结束日期').fill(text)
  await form.getByRole('button', { name: '确认创建' }).click()
  await expect(page).toHaveURL(/\/plans\/direct-plan$/)
  expect(plans).toHaveLength(1)
  expect(plans[0]).toMatchObject({ history_id: 'owned-history', candidate_ids: preserved.cards.slice(0, 2).map((c: { place: { id: string } }) => c.place.id), start_date: text, end_date: text })
  expect(assistantRequests).toBe(0)
})

test('vote panel has a readable surface and owns mobile interaction above the assistant', async ({ page }, testInfo) => {
  const plan = workbenchPlan()
  plan.summary = { voted_count: 1, joined_count: 1, complete: false, candidates: [] }; plan.expected_count = 2
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { user: { username: 'layout_owner' }, csrf_token: 'isolated-csrf' } })
    if (path === '/api/v1/plans') return route.fulfill({ json: { plans: [plan] } })
    if (path === '/api/v1/plans/workbench') return route.fulfill({ json: { plan } })
    return route.fulfill({ status: 404, json: {} })
  })
  await page.goto('/plans/workbench')
  await page.getByRole('button', { name: '去投票', exact: true }).click()
  const vote = page.getByRole('dialog', { name: '我的投票' })
  await expect(vote).toBeVisible()
  expect(await vote.evaluate(node => getComputedStyle(node).backgroundColor)).toBe('rgb(244, 250, 251)')
  const first = vote.getByLabel('首选 苏州博物馆', { exact: true })
  await first.check()
  expect(await first.evaluate(node => { const r = node.getBoundingClientRect(); return node === document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) })).toBe(true)
  if (page.viewportSize()!.width <= 700) {
    await expect(page.getByRole('button', { name: '打开操作助手', exact: true })).toHaveCount(0)
    await page.keyboard.press('Tab')
    expect(await page.evaluate(() => Boolean(document.activeElement?.closest('[role="dialog"]')))).toBe(true)
  }
  await page.screenshot({ path: testInfo.outputPath('vote-surface.png') })
  await vote.getByRole('button', { name: '收起投票面板' }).click()
  await expect(page.getByRole('button', { name: '打开操作助手', exact: true })).toBeVisible()
})

for (const cancelFirst of [false, true]) test(`guest favorites after login ${cancelFirst ? 'cancelled' : 'continued'} without losing results`, async ({ page }, testInfo) => {
  let loggedIn = false, jobs = 0, executions = 0
  let releaseIdentity!: () => void
  const identityReady = new Promise<void>(resolve => { releaseIdentity = resolve })
  const proposalBodies: Record<string, unknown>[] = []
  const place = { id: 'login-place', name: '登录前的真实对象', city: '苏州', address: '同一个地址',
    coordinate: { longitude: 120.6, latitude: 31.3, system: 'gcj02' }, map_type: '公园', facts: {}, map_url: '' }
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname
    if (path === '/api/v1/auth/me') {
      await identityReady
      return route.fulfill({ status: 401, json: { error: { code: 'authentication_required', message: '登录后可用' } } })
    }
    if (path === '/api/v1/auth/login') { loggedIn = true; return route.fulfill({ json: { user: { username: 'test_owner' }, csrf_token: 'isolated-csrf' } }) }
    if (path === '/api/v1/auth/logout') { loggedIn = false; return route.fulfill({ status: 204 }) }
    if (path === '/api/v1/discovery/jobs' && request.method() === 'POST') return route.fulfill({ json: { id: ++jobs === 1 ? 'guest-result' : 'guest-intake' } })
    if (path === '/api/v1/discovery/jobs/guest-result/history') return route.fulfill({ json: { history_id: 'saved-guest-history' } })
    if (request.method() === 'DELETE') return route.fulfill({ json: { cancelled: true } })
    if (path.startsWith('/api/v1/discovery/jobs/')) return route.fulfill({ json: {
      id: path.endsWith('guest-result') ? 'guest-result' : 'guest-intake', intent: jobs === 1 ? 'search' : 'business',
      status: 'completed', stage: '', cards: jobs === 1 ? [{ place, experience: '休闲', reason: '', sources: [], route: null, weather: null }] : [],
      reply: jobs === 1 ? '已找到这些去处。' : '', request_location: false, source: 'demo', center_name: null,
      context: { region: '苏州', origin: null, max_distance_km: null, start_date: null, end_date: null },
    } })
    if (path.endsWith('/commands/proposals')) {
      proposalBodies.push(request.postDataJSON())
      if (!loggedIn) return route.fulfill({ status: 401, json: { error: { code: 'authentication_required', message: '请先登录后执行此操作。' } } })
      return route.fulfill({ json: { request_id: 'continued-favorite', proposal: 'new-auth-proposal', question: null,
        requires_confirmation: false, actions: [{ tool: 'favorite_place', arguments: { place: 1 } }] } })
    }
    if (path.endsWith('/commands/execute')) { executions++; return route.fulfill({ json: { status: 'completed',
      steps: [{ tool: 'favorite_place', status: 'completed', result: { favorite: { destination: place } } }] } }) }
    return route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'not configured' } } })
  })
  await page.goto('/explore')
  const send = async (text: string) => { await page.keyboard.press('Alt+/'); await page.keyboard.insertText(text); await page.keyboard.press('Enter') }
  await send('苏州看看公园')
  await expect(page.getByRole('button', { name: '停止查找' })).toBeVisible()
  expect(jobs).toBe(0)
  releaseIdentity()
  const original = page.getByRole('heading', { name: place.name })
  await expect(original).toBeVisible()
  await original.evaluate(node => node.setAttribute('data-original-result', 'yes'))
  await send('收藏第一个')
  await expect(page.getByRole('dialog')).toBeVisible()
  if (cancelFirst) {
    await page.getByRole('button', { name: '关闭', exact: true }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await page.getByRole('button', { name: '账户', exact: true }).click()
  }
  const login = page.getByRole('dialog', { name: '登录 RoamBot', exact: true })
  await login.getByLabel('用户名', { exact: true }).fill('test_owner')
  await login.getByLabel('密码', { exact: true }).fill('isolated-password')
  await login.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  if (!cancelFirst) await expect.poll(() => executions).toBe(1)
  await expect(original).toHaveAttribute('data-original-result', 'yes')
  // Wait for the authenticated history attachment before checking no stale replay.
  await expect(page.locator('.discovery-workspace')).toBeVisible()
  if (cancelFirst) {
    expect(executions).toBe(0)
    expect(proposalBodies).toHaveLength(1)
  }
  await expect(original).toHaveAttribute('data-original-result', 'yes')
  expect(jobs).toBe(2)
  expect(proposalBodies).toHaveLength(cancelFirst ? 1 : 2)
  for (const body of proposalBodies) {
    expect(body.intake_id).toBe('guest-intake')
    expect(body.context).toMatchObject({ discovery_job_id: 'guest-result', visible_places: [{ id: place.id, name: place.name }] })
  }
  await expect(page.getByRole('log').getByText('苏州看看公园', { exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('login-keeps-results.png') })
  await page.getByRole('button', { name: '账户', exact: true }).click()
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: place.name })).toHaveCount(0)
  expect(executions).toBe(cancelFirst ? 0 : 1)
})

test('card rail and chat dock scroll independently without bars or blocked actions', async ({ page }, testInfo) => {
  let sequence = 0
  const cards = Array.from({ length: 7 }, (_, i) => ({
    place: { id: 'layout-' + i, name: '去处' + (i + 1), city: '苏州', address: '示例地址',
      coordinate: { longitude: 120.6, latitude: 31.3, system: 'gcj02' }, map_type: '公园', map_url: '',
      facts: { opentime_week: '周一至周日 09:00-18:00' } },
    experience: '休闲', reason: '', sources: [], route: null, weather: null,
  }))
  await page.route('**/api/v1/**', route => {
    const request = route.request(), path = new URL(request.url()).pathname
    if (path === '/api/v1/auth/me') return route.fulfill({ status: 401, json: { error: { code: 'authentication_required', message: '登录后可用' } } })
    if (path === '/api/v1/discovery/jobs' && request.method() === 'POST') return route.fulfill({ json: { id: 'layout-' + (++sequence) } })
    if (path.startsWith('/api/v1/discovery/jobs/layout-')) return route.fulfill({ json: {
      id: 'layout-' + sequence, intent: 'search', status: 'completed', stage: '', cards,
      reply: '已找到这些去处。', request_location: false, center_name: null, source: 'demo',
      context: { region: '苏州', origin: null, max_distance_km: null, start_date: null, end_date: null },
    } })
    return route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'not configured' } } })
  })
  await page.goto('/explore')
  for (const message of ['苏州看看公园', '保留公园，轻松一些', '还是在苏州', '看看其他选择']) {
    await page.keyboard.press('Alt+/'); await page.keyboard.insertText(message); await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { name: message, exact: true })).toBeVisible()
    await expect(page.locator('.discovery-status [role=status]')).toHaveCount(0)
    await expect(page.locator('.discovery-conversation .assistant')).toHaveCount(sequence)
  }
  const rail = page.getByRole('region', { name: '推荐去处', exact: true })
  await expect(rail).toHaveCSS('scrollbar-width', 'none')
  await expect(page.getByRole('log')).toHaveCSS('scrollbar-width', 'none')
  const card = rail.locator('.discovery-card').first()
  await expect(card).toHaveCSS('padding', (testInfo.project.name.startsWith('mobile') ? '18' : '22') + 'px')
  await expect(card).toHaveCSS('min-height', '300px')
  expect((await card.boundingBox())!.height).toBeLessThanOrEqual(350)
  expect(Math.round((await card.boundingBox())!.width)).toBe(Math.round(Math.min(310, page.viewportSize()!.width * .82)))
  await rail.scrollIntoViewIfNeeded(); await rail.focus(); await page.keyboard.press('ArrowRight')
  await expect.poll(() => rail.evaluate(node => node.scrollLeft)).toBeGreaterThan(100)
  await page.keyboard.press('Home')
  await expect.poll(() => rail.evaluate(node => node.scrollLeft)).toBeLessThan(2)
  await page.getByRole('button', { name: '推荐去处向右滑动' }).click()
  await expect.poll(() => rail.evaluate(node => node.scrollLeft)).toBeGreaterThan(100)
  await rail.focus(); await page.keyboard.press('Home')
  await expect.poll(() => rail.evaluate(node => node.scrollLeft)).toBeLessThan(2)
  const box = (await card.getByRole('button', { name: '了解去处1' }).boundingBox())!
  const dragY = Math.max(box.y + 65, 150)
  await page.mouse.move(box.x + box.width * .8, dragY); await page.mouse.down()
  await page.mouse.move(box.x + 15, dragY, { steps: 12 }); await page.mouse.up()
  await expect.poll(() => rail.evaluate(node => node.scrollLeft)).toBeGreaterThan(100)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await rail.focus(); await page.keyboard.press('Home')
  await expect.poll(() => rail.evaluate(node => node.scrollLeft)).toBeLessThan(2)
  await rail.hover(); await page.mouse.wheel(0, 260)
  await expect.poll(() => rail.evaluate(node => node.scrollLeft)).toBeGreaterThan(100)
  await rail.focus(); await page.keyboard.press('Home')
  await expect.poll(() => rail.evaluate(node => node.scrollLeft)).toBeLessThan(2)
  const action = card.getByRole('button', { name: '加入比较', exact: true })
  await action.scrollIntoViewIfNeeded()
  expect(await action.evaluate(node => {
    const r = node.getBoundingClientRect()
    return [2, r.width / 2, r.width - 2].every(x => node.contains(document.elementFromPoint(r.x + x, r.y + r.height / 2)))
  })).toBe(true)
  await action.click()
  await expect(card.getByRole('button', { name: '已选入比较' })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  const log = page.getByRole('log')
  await log.hover(); await page.mouse.wheel(0, -600)
  await expect.poll(() => log.evaluate(node => node.scrollTop)).toBeLessThan(5)
  await page.locator('.discovery-selection').scrollIntoViewIfNeeded()
  const dock = (await page.locator('.discovery-input').boundingBox())!
  const selection = (await page.locator('.discovery-selection').boundingBox())!
  expect(selection.y + selection.height + 12).toBeLessThan(dock.y)
  await page.screenshot({ path: testInfo.outputPath('rail-chat-layout.png') })
})

test('nearby query requests browser location and resumes without a second user action', async ({ page, context }, testInfo) => {
  // Deliberately synthetic location and API responses: never a real GPS/Provider claim.
  await context.grantPermissions(['geolocation'])
  await context.setGeolocation({ latitude: 31.3, longitude: 120.6 })
  const requests: Record<string, unknown>[] = []
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/api/v1/auth/me') return route.fulfill({ status: 401, json: { error: { code: 'authentication_required', message: '登录后可用' } } })
    if (path === '/api/v1/discovery/jobs' && request.method() === 'POST') {
      requests.push(request.postDataJSON())
      return route.fulfill({ json: { id: 'location-job-' + requests.length } })
    }
    if (path.includes('/discovery/jobs/location-job-')) {
      const located = path.endsWith('-2')
      return route.fulfill({ json: { id: 'location-job-' + (located ? 2 : 1), intent: 'search',
        status: 'completed', stage: '', reply: located ? '已找到这些去处。' : '',
        request_location: !located, context: { origin: null, region: '苏州', max_distance_km: 5 },
        center_name: located ? '当前位置' : null, source: 'demo', cards: located ? [{
          place: { id: 'location-place', name: '定位接续示例绿地', city: '苏州', address: '模拟地址',
            coordinate: { latitude: 31.3, longitude: 120.6, system: 'gcj02' }, map_type: '公园', facts: {}, map_url: '' },
          experience: '湖边放松', reason: '此卡片仅用于验证浏览器定位授权后自动接续查询，不代表真实地点推荐。',
          sources: [], weather: null, route: { distance_km: 2, duration_minutes: 25, mode: 'walking' },
        }] : [] } })
    }
    return route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'not configured' } } })
  })
  await page.goto('/explore')
  await page.keyboard.press('Alt+/')
  await page.keyboard.insertText('苏州附近放松一下的地方')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: '定位接续示例绿地' })).toBeVisible()
  expect(requests).toHaveLength(2)
  expect(requests[1]).toMatchObject({ message: requests[0].message, previous_id: 'location-job-1',
    location: { latitude: 31.3, longitude: 120.6, system: 'wgs84' } })
  await expect(page.getByRole('log').locator('.user')).toHaveCount(1)
  await expect(page.getByRole('button', { name: '重试定位' })).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('automatic-location-mock.png') })
})

test('free-form discovery appends stable cards and preserves detail/map history', async ({ page }, testInfo) => {
  let append = false
  let submitted: Record<string, unknown> | undefined
  const card = (id: string, name: string, experience: string) => ({
    place: { id, name, address: '实际地址', city: '苏州', coordinate: { longitude: 120.6, latitude: 31.3, system: 'gcj02' },
      map_type: '开放类别', facts: {}, map_url: 'https://www.amap.com/detail/' + id },
    experience, reason: `${name}的公开介绍提供了具体场地信息，结合这次希望轻松休息的想法，可以作为不同的选择。`,
    sources: [{ id: 'proof-' + id, kind: 'search_excerpt', title: '公开介绍', url: 'https://example.org/' + id }], route: null, weather: null,
  })
  const cards = [card('p1', '独立书店', '翻书休息'), card('p2', '湖边绿地', '水边放松'), card('p3', '城市展览', '看看展览')]
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/auth/me') return route.fulfill({ status: 401, json: { error: { code: 'authentication_required', message: '登录后可用' } } })
    if (path === '/api/v1/discovery/jobs' && route.request().method() === 'POST') {
      submitted = route.request().postDataJSON(); return route.fulfill({ json: { id: 'test-job' } })
    }
    if (path === '/api/v1/discovery/jobs/test-job') return route.fulfill({ json: {
      id: 'test-job', status: append ? 'completed' : 'running', stage: '正在核对地点资料',
      cards: append ? cards : cards.slice(0, 1), reply: append ? '已找到不同的去处。' : '', request_location: false,
      center_name: null, context: { region: '苏州', origin: null, start_date: null, end_date: null, max_distance_km: null }, source: 'demo',
    } })
    if (path === '/api/v1/maps/config') return route.fulfill({ json: { enabled: false } })
    return route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'not configured' } } })
  })
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/explore')
  await page.keyboard.press('Alt+/')
  await expect(page.getByRole('textbox', { name: '继续补充条件' })).toBeFocused()
  await page.keyboard.insertText('我想在苏州找些可以坐一会儿、换换心情的地方')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: '独立书店' })).toBeVisible()
  expect(submitted).toEqual({ message: '我想在苏州找些可以坐一会儿、换换心情的地方', previous_id: null,
    view: { focused_id: null, selected_ids: [], layer: 'results' } })
  const first = page.locator('[data-place-id="p1"]')
  await page.evaluate(async () => {
    await document.fonts.ready
    await Promise.all(document.getAnimations().filter(animation =>
      animation.effect?.getComputedTiming().iterations !== Infinity).map(animation => animation.finished.catch(() => undefined)))
  })
  const before = await first.boundingBox()
  append = true
  await expect(page.locator('[data-place-id]')).toHaveCount(3)
  const after = await first.boundingBox()
  expect(Math.abs(before!.x - after!.x)).toBeLessThan(1)
  expect(Math.abs(before!.y - after!.y)).toBeLessThan(1)
  await page.evaluate(() => Promise.all(document.getAnimations().filter(animation =>
    animation.effect?.getComputedTiming().iterations !== Infinity).map(animation => animation.finished.catch(() => undefined))))
  const positions = await page.locator('[data-place-id]').evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().top))
  expect(Math.max(...positions) - Math.min(...positions)).toBeLessThan(1)
  await expect(page.getByText(/匹配指数|暂无评分|平均.*km/)).toHaveCount(0)
  await expect(first.getByRole('link')).toHaveCount(0)
  await expect(first.locator('.discovery-reason')).toHaveCount(0)
  expect((await first.boundingBox())!.height).toBeLessThan(340)
  const toggle = first.getByRole('button', { name: '加入比较', exact: true })
  await toggle.scrollIntoViewIfNeeded()
  for (const point of [{ x: .5, y: .5 }, { x: .08, y: .5 }, { x: .92, y: .5 }]) {
    expect(await toggle.evaluate((node, position) => {
      const rect = node.getBoundingClientRect()
      return node.contains(document.elementFromPoint(rect.x + rect.width * position.x, rect.y + rect.height * position.y))
    }, point)).toBe(true)
  }
  await toggle.click()
  await expect(first.getByRole('button', { name: '已选入比较' })).toHaveAttribute('aria-pressed', 'true')
  await first.getByRole('button', { name: '已选入比较' }).press('Space')
  await expect(first.getByRole('button', { name: '加入比较', exact: true })).toHaveAttribute('aria-pressed', 'false')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await first.getByRole('button', { name: '了解独立书店' }).click()
  await expect(page.getByRole('dialog', { name: '独立书店详情' })).toBeVisible()
  await page.getByRole('button', { name: '查看位置', exact: true }).click()
  await expect(page.getByRole('dialog', { name: /位置/ })).toBeVisible()
  await page.goBack()
  await expect(page.getByRole('dialog', { name: /位置/ })).toHaveCount(0)
  await expect(page.getByRole('dialog', { name: '独立书店详情' })).toBeVisible()
  await page.goBack()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
  await expect(first).toBeVisible()
  expect(errors).toEqual([])
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
  await page.screenshot({ path: testInfo.outputPath('discovery.png') })
})

test('chat controls new results and nested layers; footer hit targets remain independent', async ({ page }) => {
  let jobs = 0
  let message = ''
  const contexts: Record<string, unknown>[] = []
  const cards = ['独立书店', '湖边绿地'].map((name, i) => ({
    place: { id: 'p' + (i + 1), name, address: '实际地址', city: '苏州',
      coordinate: { longitude: 120.6, latitude: 31.3, system: 'gcj02' },
      map_type: '开放类别', facts: {}, map_url: 'https://www.amap.com/detail/' + i },
    experience: i ? '水边放松' : '翻书休息', reason: `${name}的公开介绍提供具体的场地信息，结合这次希望放松的想法，可以进一步比较选择。`,
    sources: [], route: null, weather: null,
  }))
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/auth/me') return route.fulfill({ status: 401, json: { error: { code: 'authentication_required', message: '登录后可用' } } })
    if (path === '/api/v1/discovery/jobs' && route.request().method() === 'POST') {
      message = route.request().postDataJSON().message
      return route.fulfill({ json: { id: 'job-' + (++jobs) } })
    }
    if (/\/discovery\/jobs\/job-/.test(path)) return route.fulfill({ json: {
      id: 'job-' + jobs, intent: jobs === 1 ? 'search' : 'business', status: 'completed', stage: '',
      cards: jobs === 1 ? cards : [], reply: '', request_location: false, center_name: null,
      context: { region: '苏州', origin: null, start_date: null, end_date: null, max_distance_km: null }, source: 'demo',
    } })
    if (path.endsWith('/commands/proposals')) {
      contexts.push(route.request().postDataJSON().context)
      return route.fulfill({ json: { request_id: 'action-' + jobs, proposal: 'proposal-' + jobs,
        question: null, requires_confirmation: false, actions: [] } })
    }
    if (path.endsWith('/commands/execute')) {
      const effects = message.includes('比较') ? [
        { tool: 'show_comparison', arguments: { ids: ['p1', 'p2'] } },
      ] : message.includes('位置') ? [{ tool: 'open_map', arguments: { id: 'p2' } }]
        : [{ tool: 'close_layer', arguments: {} }]
      return route.fulfill({ json: { status: 'completed', steps: effects.map(effect => ({
        tool: effect.tool, status: 'completed', result: { effect },
      })) } })
    }
    if (path === '/api/v1/maps/config') return route.fulfill({ json: { enabled: false } })
    return route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'not configured' } } })
  })
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  async function chat(text: string) {
    await expect(page.locator('.studio-composer[data-busy="true"]:visible')).toHaveCount(0)
    await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
    await page.keyboard.press('Alt+/')
    await expect(page.locator('[data-command-input]:focus')).toHaveCount(1)
    await page.keyboard.insertText(text)
    const execution = text === '苏州找些不同去处' ? null : page.waitForResponse(response => response.url().endsWith('/commands/execute'))
    await page.keyboard.press('Enter')
    // The initial discovery message does not execute a business command.
    if (execution) await execution
    await expect(page.locator('.studio-composer[data-busy="true"]:visible')).toHaveCount(0)
  }
  await page.goto('/explore')
  await chat('苏州找些不同去处')
  const first = page.locator('[data-place-id="p1"]')
  await expect(first).toBeVisible()
  await first.evaluate(node => node.setAttribute('data-retained', 'yes'))
  const select = first.getByRole('button', { name: '加入比较', exact: true })
  await select.scrollIntoViewIfNeeded()
  // Text centre, then outer button edge, then keyboard: each changes only selection.
  expect(await select.evaluate(node => {
    const r = node.getBoundingClientRect()
    return [[r.x + r.width / 2, r.y + r.height / 2], [r.x + 2, r.y + r.height / 2]]
      .every(([x, y]) => node.contains(document.elementFromPoint(x, y)))
  })).toBe(true)
  await select.click()
  const chosen = first.getByRole('button', { name: '已选入比较' })
  await chosen.click({ position: { x: 2, y: 12 } })
  await select.focus(); await page.keyboard.press('Space')
  await expect(first.getByRole('button', { name: '已选入比较' })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await chat('看第二个的位置')
  await expect(page.getByRole('dialog', { name: /位置/ })).toBeVisible()
  expect(contexts.at(-1)).toMatchObject({ discovery_job_id: 'job-1', selected_ids: ['p1'], layer: 'results' })
  await chat('关闭地图')
  await expect(page.getByRole('dialog', { name: /位置/ })).toHaveCount(0)
  await expect(page.getByRole('dialog', { name: '湖边绿地详情' })).toBeVisible()
  expect(contexts.at(-1)).toMatchObject({ discovery_job_id: 'job-1', focused_id: 'p2', layer: 'map' })
  await chat('关闭详情')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await chat('选择前两个比较')
  await expect(page.getByRole('dialog', { name: '地点对比' })).toBeVisible()
  await page.goBack()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(first).toHaveAttribute('data-retained', 'yes')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('苏州找些不同去处')
  expect(contexts).toHaveLength(4)
  expect(errors).toEqual([])
})
