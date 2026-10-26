import { installLegacyAssistantFixture, fulfillApiFixture } from './helpers'
import { expect, test } from '@playwright/test'
import { studioResponse } from '../tests/fixtures/studio'
import { createStudioState } from '../src/features/studio/studioState'
import { chinaDate } from '../src/features/search/formState'
import { workbenchPlan } from '../tests/fixtures/workbenchPlan'
import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', route => fulfillApiFixture(route, { json: route.request().url().endsWith('/maps/config') ? { enabled: false }
    : route.request().url().endsWith('/recommendations') ? studioResponse : { user: null, plans: [], histories: [], favorites: [] } }))
  const draft = { ...createStudioState().draft, mainOrigin: '苏州站', startDate: chinaDate(1), endDate: chinaDate(1), sceneryTypes: ['lake' as const] }
  await page.addInitScript(({ result, draft }) => {
    if (!sessionStorage.getItem('frontendFixtureSeeded')) {
      sessionStorage.setItem('roambot.session.search-result.v1', JSON.stringify(result))
      sessionStorage.setItem('roambot.session.search-draft.v1', JSON.stringify(draft))
      sessionStorage.setItem('frontendFixtureSeeded', '1')
    }
    const trace: unknown[] = []
    Object.assign(window, { frontendHistoryTrace: trace })
    const motion: unknown[] = []
    Object.assign(window, { frontendMotionTrace: motion })
    const animate = Element.prototype.animate
    Element.prototype.animate = function (...args) {
      if (this.classList.contains('route-content')) motion.push({ kind: 'route', time: performance.now(), path: location.pathname })
      return animate.apply(this, args)
    }
    if (document.startViewTransition) {
      const start = document.startViewTransition.bind(document)
      document.startViewTransition = (...args) => {
        motion.push({ kind: 'native-start', time: performance.now() })
        const transition = start(...args)
        void transition.finished.then(() => motion.push({ kind: 'native-finish', time: performance.now() }))
        return transition
      }
    }
    for (const method of ['pushState', 'replaceState'] as const) {
      const original = history[method].bind(history)
      history[method] = (...args) => { original(...args); trace.push({ method, state: history.state }) }
    }
    window.addEventListener('popstate', () => trace.push({ method: 'popstate', state: history.state }))
    new MutationObserver(() => {
      const phase = document.querySelector('.spatial-workspace')?.getAttribute('data-workspace-phase')
      if (phase) trace.push({ method: 'render', phase, details: document.querySelectorAll('[data-detail-id]').length,
        maps: document.querySelectorAll('.location-backdrop:not([data-exit-snapshot])').length,
        exits: document.querySelectorAll('[data-exit-snapshot]').length })
    }).observe(document, { subtree: true, attributes: true, attributeFilter: ['data-workspace-phase'] })
  }, { result: studioResponse, draft })
})
test.beforeEach(async ({ page }) => { await installLegacyAssistantFixture(page) })


for (const width of [1920, 1280, 390]) for (const reduced of [false, true]) {
test(`plan entry and layer conversations ${width} reduced=${reduced}`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 900 }); await page.emulateMedia({ reducedMotion: reduced ? 'reduce' : 'no-preference' })
  await page.route('**/api/v1/auth/me', route => fulfillApiFixture(route, { json: { user: { username: 'fixture_user' }, csrf_token: 'synthetic' } }))
  await page.route('**/api/v1/recommendations', route => fulfillApiFixture(route, { json: { ...studioResponse, history_id: 'fresh-history', assistant_context: 'synthetic-context' } }))
  let creations = 0
  await page.route('**/api/v1/plans', route => {
    if (route.request().method() !== 'POST') return fulfillApiFixture(route, { json: { plans: [] } })
    creations++; expect(route.request().postDataJSON()).toMatchObject({ history_id: 'fresh-history', candidate_ids: ['place-0', 'place-1'] })
    return fulfillApiFixture(route, { json: { plan: { id: 'fixture-plan' } } })
  })
  await page.route('**/api/v1/plans/fixture-plan', route => fulfillApiFixture(route, { json: { plan: workbenchPlan() } }))
  const turns: { message: string; focused_destination_id?: string }[] = []
  await page.route('**/api/v1/assistant/turns', route => {
    const body = route.request().postDataJSON(); turns.push(body)
    return fulfillApiFixture(route, { json: { revision: body.revision, patch: { max_distance_km: turns.length === 1 ? 80 : 100 }, reply: '已收到这条条件', source: 'demo' } })
  })
  await page.goto('/plans')
  await page.getByRole('link', { name: '发起同行计划', exact: true }).click()
  await expect(page).toHaveURL(/\/explore$/)
  await expect(page.getByRole('textbox', { name: '继续补充条件' })).toBeVisible()
  await page.goto('/recommend')
  await page.getByRole('button', { name: '更多功能', exact: true }).click()
  await page.getByRole('button', { name: '发起同行挑选', exact: true }).click()
  await expect(page.getByText('同行挑选中', { exact: false })).toBeVisible()
  await expect(page.getByRole('textbox', { name: '继续补充条件' })).toBeVisible()
  await expect(page.getByRole('button', { name: '发起同行计划', exact: true })).toBeDisabled()
  await page.locator('.candidate-toggle').nth(0).click(); await page.locator('.candidate-toggle').nth(1).click()
  await page.getByRole('button', { name: '发起同行计划', exact: true }).click()
  await page.getByRole('button', { name: '更新推荐并继续', exact: true }).click()
  await expect(page.getByRole('button', { name: '确认创建', exact: true })).toBeEnabled()
  expect(creations).toBe(0)
  await page.screenshot({ path: info.outputPath('create-after-refresh.png') })
  await page.getByRole('dialog', { name: '创建同行计划' }).getByRole('button', { name: '取消', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '创建同行计划' })).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('selected-plan-entry.png') })
  const normal = page.getByRole('textbox', { name: '继续补充条件' }); await normal.fill('尚未发送的查询文字')
  await page.getByRole('button', { name: /^了解/ }).first().click(); await settle(page, '.destination-detail-layer')
  const historyLength = await page.evaluate(() => history.length)
  const detailOrb = page.getByRole('button', { name: '打开详情对话', exact: true })
  const hit = async (node: import('@playwright/test').Locator) => node.evaluate(el => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, hit: el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)) } })
  const orb = await hit(detailOrb); expect(orb.hit).toBe(true); expect(orb.x).toBeGreaterThanOrEqual(0); expect(orb.x + (await detailOrb.boundingBox())!.width).toBeLessThanOrEqual(width); expect(orb.y).toBeGreaterThan(900 * .5); expect(orb.y + (await detailOrb.boundingBox())!.height).toBeLessThanOrEqual(900 - 12)
  await detailOrb.click()
  const detailChat = page.getByRole('region', { name: '详情对话', exact: true })
  await settle(page, '.layer-chat-panel')
  const input = detailChat.getByRole('textbox', { name: '继续补充条件' }); expect((await hit(input)).hit).toBe(true)
  await input.fill('详情里继续修改条件'); await detailChat.getByRole('button', { name: '发送消息' }).click()
  await expect(detailChat.getByText('已收到这条条件')).toBeVisible()
  await expect(page.locator('.condition-puzzle-compact')).toContainText('80 km 内')
  expect(turns[0]).toMatchObject({ message: '详情里继续修改条件', focused_destination_id: 'place-0' })
  await input.fill('收起后保留'); await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: '金鸡湖景区详情' })).toBeVisible()
  await detailOrb.click(); await expect(detailChat.getByRole('textbox', { name: '继续补充条件' })).toHaveValue('收起后保留')
  await settle(page, '.layer-conversation')
  await page.screenshot({ path: info.outputPath('detail-conversation.png') })
  await page.keyboard.press('Escape')
  expect(await page.evaluate(() => history.length)).toBe(historyLength)
  await page.getByRole('button', { name: '查看位置', exact: true }).click(); await settle(page, '.location-backdrop')
  const mapOrb = page.getByRole('button', { name: '打开地图对话', exact: true }); expect((await hit(mapOrb)).hit).toBe(true)
  await mapOrb.click(); const mapChat = page.getByRole('region', { name: '地图对话', exact: true })
  await settle(page, '.location-backdrop .layer-chat-panel')
  await mapChat.getByRole('textbox', { name: '继续补充条件' }).fill('地图里继续修改条件'); await mapChat.getByRole('button', { name: '发送消息' }).click()
  await expect.poll(() => turns.length).toBe(2); expect(turns[1]).toMatchObject({ message: '地图里继续修改条件', focused_destination_id: 'place-0' })
  await expect(page.locator('.condition-puzzle-compact')).toContainText('100 km 内')
  expect((await hit(mapChat.getByRole('textbox', { name: '继续补充条件' }))).hit).toBe(true)
  await page.screenshot({ path: info.outputPath('map-conversation.png') })
  await page.keyboard.press('Escape'); await expect(page.getByRole('dialog', { name: '景点位置' })).toBeVisible()
  await expect(mapOrb).toBeFocused()
  await page.getByRole('button', { name: '关闭地图' }).click(); await expect(page.getByRole('dialog', { name: '景点位置' })).toHaveCount(0)
  await page.keyboard.press('Escape'); await expect(page.getByRole('dialog', { name: '金鸡湖景区详情' })).toHaveCount(0)
  await expect(normal).toBeVisible(); await expect(normal).toHaveValue('尚未发送的查询文字')
  expect(await page.evaluate(() => history.length)).toBe(historyLength + 1)
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await page.getByRole('button', { name: '更新推荐', exact: true }).click()
  await expect(page.getByRole('button', { name: '发起同行计划', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '发起同行计划', exact: true }).click(); await page.getByRole('button', { name: '确认创建', exact: true }).click()
  await expect(page).toHaveURL(/\/plans\/fixture-plan$/); expect(creations).toBe(1)
})
}

test('plan entry continues after login without discarding selected places', async ({ page }) => {
  await page.route('**/api/v1/auth/login', route => fulfillApiFixture(route, { json: { user: { username: 'fixture_user' }, csrf_token: 'synthetic' } }))
  await page.goto('/recommend'); await page.locator('.candidate-toggle').nth(0).click(); await page.locator('.candidate-toggle').nth(1).click()
  await page.getByRole('button', { name: '发起同行计划', exact: true }).click()
  const auth = page.getByRole('dialog', { name: '登录 RoamBot' })
  await auth.getByLabel('用户名', { exact: true }).fill('fixture_user'); await auth.getByLabel('密码', { exact: true }).fill('synthetic-password')
  await auth.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '创建同行计划' })).toBeVisible()
  await expect(page.getByRole('button', { name: '更新推荐并继续', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '查看对比（2）' })).toBeVisible()
})

test('changed or failed plan refresh never creates a plan or reuses missing candidates', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => fulfillApiFixture(route, { json: { user: { username: 'fixture_user' }, csrf_token: 'synthetic' } }))
  let refresh = 0, creations = 0
  await page.route('**/api/v1/recommendations', route => ++refresh === 1
    ? fulfillApiFixture(route, { status: 503, json: { detail: 'unavailable' } })
    : fulfillApiFixture(route, { json: { ...studioResponse, items: studioResponse.items.slice(1), history_id: 'new-history' } }))
  await page.route('**/api/v1/plans', route => { if (route.request().method() === 'POST') creations++; return fulfillApiFixture(route, { json: { plans: [] } }) })
  await page.goto('/recommend'); await page.locator('.candidate-toggle').nth(0).click(); await page.locator('.candidate-toggle').nth(1).click()
  await page.getByRole('button', { name: '发起同行计划', exact: true }).click()
  await page.getByRole('button', { name: '更新推荐并继续', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '创建同行计划' }).getByRole('alert')).toBeVisible()
  await expect(page.getByRole('button', { name: '查看对比（2）' })).toBeVisible()
  await page.getByRole('button', { name: '更新推荐并继续', exact: true }).click()
  await expect(page.getByRole('button', { name: '重新选择地点', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '确认创建', exact: true })).toHaveCount(0)
  expect(creations).toBe(0)
  await page.getByRole('button', { name: '重新选择地点', exact: true }).click()
  await expect(page.getByRole('button', { name: '发起同行计划', exact: true })).toBeDisabled()
})

for (const [width, reduced] of [[1280, false], [390, false], [390, true]] as const) {
test(`conversation pocket fade ${width} reduced=${reduced}`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 900 }); await page.emulateMedia({ reducedMotion: reduced ? 'reduce' : 'no-preference' })
  await page.route('**/api/v1/assistant/turns', route => fulfillApiFixture(route, { json: { revision: route.request().postDataJSON().revision,
    reply: '这是一段用于观察滚动交接的长对话记录，内容经过顶部时应逐渐淡出。'.repeat(24), patch: {}, source: 'demo' } }))
  await page.goto('/recommend'); await page.getByRole('button', { name: /^了解/ }).first().click()
  await page.getByRole('button', { name: '打开详情对话' }).click()
  const chat = page.getByRole('region', { name: '详情对话', exact: true }), records = chat.getByRole('region', { name: '详情对话记录' })
  const input = chat.getByRole('textbox', { name: '继续补充条件' })
  await input.fill('看看更详细的信息'); await chat.getByRole('button', { name: '发送消息' }).click()
  await expect.poll(() => records.evaluate(node => node.scrollHeight > node.clientHeight)).toBe(true)
  await records.evaluate(node => { node.scrollTop = 0 })
  await expect(records).toHaveAttribute('data-scrolled', 'false')
  const initial = (await input.boundingBox())!
  await records.hover(); await page.mouse.wheel(0, 160)
  await expect.poll(() => records.evaluate(node => node.scrollTop)).toBeGreaterThan(40)
  await expect(records).toHaveAttribute('data-scrolled', 'true')
  const middle = (await input.boundingBox())!
  expect(Math.abs(initial.y - middle.y)).toBeLessThan(1)
  expect(await input.evaluate(el => { const r=el.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===el })).toBe(true)
  await page.screenshot({ path: info.outputPath('conversation-pocket.png') })
  await records.evaluate(node => { node.scrollTop = 0 })
  await expect(records).toHaveAttribute('data-scrolled', 'false')
  await page.screenshot({ path: info.outputPath('conversation-pocket-top.png') })
  await page.keyboard.press('Escape'); await expect(page.getByRole('dialog', { name: '金鸡湖景区详情' })).toBeVisible()
})
}

for (const width of [1920, 1280, 390]) {
test(`candidate dock action alignment ${width}`, async ({ page }, info) => {
  await page.setViewportSize({width,height:900})
  await page.goto('/recommend')
  await settle(page, '.route-content')
  const dock=page.getByRole('complementary',{name:'已选候选'})
  for(let count=0;count<=3;count++) {
    if(count) await page.locator('.candidate-toggle').nth(count-1).click()
    await dock.evaluate(node => node.scrollIntoView({ block: 'center', behavior: 'instant' }))
    const primary=dock.getByRole('button',{name:'发起同行计划',exact:true}),compare=dock.getByRole('button',{name:`查看对比（${count}）`})
    await expect(primary).toBeVisible();await expect(compare).toBeVisible()
    if(count<2) {await expect(primary).toBeDisabled();await expect(compare).toBeDisabled()}
    else {await expect(primary).toBeEnabled();await expect(compare).toBeEnabled()}
    const p=(await primary.boundingBox())!,c=(await compare.boundingBox())!
    await page.screenshot({path:info.outputPath(`dock-${count}.png`)})
    expect(Math.abs(p.y-c.y),`count=${count}: action buttons must share a row`).toBeLessThan(2)
    expect(Math.abs(p.height-c.height)).toBeLessThan(2)
    expect(p.x+p.width).toBeLessThanOrEqual(c.x+1)
    expect(c.x+c.width).toBeLessThanOrEqual(width)
    for(const button of [primary,compare]) expect(await button.evaluate(el=>{
      const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))
    })).toBe(true)
    if(count<2) {
      const hint=(await dock.getByText(`再选 ${2-count} 个地点即可发起`).boundingBox())!
      expect(hint.y).toBeGreaterThanOrEqual(Math.max(p.y+p.height,c.y+c.height))
      const fonts=await dock.evaluate(node=>({hint:parseFloat(getComputedStyle(node.querySelector('.candidate-dock-hint')!).fontSize),button:parseFloat(getComputedStyle(node.querySelector('.primary-button')!).fontSize)}))
      expect(fonts.hint).toBeLessThan(fonts.button)
    }
  }
  await dock.getByRole('button',{name:'查看对比（3）'}).click()
  await expect(page.getByRole('dialog',{name:'候选对比'})).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase','results')
})
}

for (const [width,reduced] of [[1920,false],[1280,false],[390,false],[390,true]] as const) {
test(`draggable conversation grows to the right ${width} reduced=${reduced}`, async ({ page }, info) => {
  await page.setViewportSize({width,height:900});await page.emulateMedia({reducedMotion:reduced?'reduce':'no-preference'});await page.goto('/recommend')
  await page.getByRole('button',{name:/^了解/}).first().click();await settle(page,'.destination-detail-layer')
  const orb=page.getByRole('button',{name:'打开详情对话',exact:true})
  const initial=(await orb.boundingBox())!
  await page.mouse.move(initial.x+initial.width/2,initial.y+initial.height/2);await page.mouse.down();await page.mouse.move(80,initial.y+initial.height/2,{steps:12});await page.mouse.up()
  await expect(orb).toHaveAttribute('aria-expanded','false')
  const left=(await orb.boundingBox())!
  await page.mouse.move(left.x+left.width/2,left.y+left.height/2);await page.mouse.down();await page.mouse.move(width-38,left.y+left.height/2,{steps:12});await page.mouse.up()
  await expect(orb).toHaveAttribute('aria-expanded','false')
  const right=(await orb.boundingBox())!;expect(right.x).toBeGreaterThan(width-100)
  await orb.click();const chat=page.getByRole('region',{name:'详情对话',exact:true})
  if(!reduced) {
    await page.locator('.layer-conversation').evaluate(node=>{for(const animation of node.getAnimations({subtree:true})){animation.pause();animation.currentTime=150}})
    await page.screenshot({path:info.outputPath('right-edge-growth-mid.png')})
    await page.locator('.layer-conversation').evaluate(node=>{for(const animation of node.getAnimations({subtree:true}))animation.play()})
  }
  await settle(page,'.layer-conversation')
  const sphere=(await page.getByRole('button',{name:'收起详情对话',exact:true}).last().boundingBox())!,panel=(await chat.boundingBox())!
  expect(sphere.x).toBeLessThan(right.x-100)
  expect(panel.x).toBeGreaterThanOrEqual(sphere.x+sphere.width)
  expect(panel.x+panel.width).toBeLessThanOrEqual(width)
  expect(panel.y).toBeGreaterThanOrEqual(0);expect(panel.y+panel.height).toBeLessThanOrEqual(900)
  await chat.getByRole('textbox',{name:'继续补充条件'}).fill('拖动后保留')
  await page.screenshot({path:info.outputPath('right-edge-growth.png')})
  const moving=page.getByRole('button',{name:'收起详情对话',exact:true}).last()
  await page.mouse.move(sphere.x+26,sphere.y+26);await page.mouse.down();await page.mouse.move(sphere.x+26,sphere.y-140,{steps:10});await page.mouse.up()
  const moved=(await moving.boundingBox())!,movedPanel=(await chat.boundingBox())!
  expect(moved.y).toBeLessThan(sphere.y-80);expect(movedPanel.y).toBeLessThan(panel.y-80)
  await expect(chat.getByRole('textbox',{name:'继续补充条件'})).toHaveValue('拖动后保留')
  await page.keyboard.press('Escape');await settle(page,'.layer-conversation')
  await expect(page.getByRole('dialog',{name:'金鸡湖景区详情'})).toBeVisible()
  await expect(orb).toBeFocused()
  const keyboardBefore=(await orb.boundingBox())!;await page.keyboard.press('ArrowUp');await settle(page,'.layer-conversation')
  expect((await orb.boundingBox())!.y).toBeLessThan(keyboardBefore.y-10)
  await orb.click();await settle(page,'.layer-conversation')
  await page.getByRole('button',{name:'查看位置',exact:true}).click();await settle(page,'.location-backdrop')
  const map=page.getByRole('button',{name:'打开地图对话',exact:true});await map.click();await settle(page,'.location-backdrop .layer-conversation')
  const mapPanel=page.getByRole('region',{name:'地图对话',exact:true})
  await expect(mapPanel.getByRole('textbox',{name:'继续补充条件'})).toBeVisible()
  const mapSphere=page.getByRole('button',{name:'收起地图对话',exact:true}).last(),mapBefore=(await mapSphere.boundingBox())!
  await page.mouse.move(mapBefore.x+26,mapBefore.y+26);await page.mouse.down();await page.mouse.move(mapBefore.x+26,mapBefore.y-120,{steps:10});await page.mouse.up()
  expect((await mapSphere.boundingBox())!.y).toBeLessThan(mapBefore.y-80)
  const movedMap=(await mapPanel.boundingBox())!;expect(movedMap.x).toBeGreaterThanOrEqual(0);expect(movedMap.x+movedMap.width).toBeLessThanOrEqual(width)
  await page.screenshot({path:info.outputPath('map-dragged.png')})
  await page.keyboard.press('Escape');await expect(page.getByRole('dialog',{name:'景点位置'})).toBeVisible()
})
}

test('conversation orb touch drag does not toggle or scroll its background', async ({ page }) => {
  await page.setViewportSize({width:390,height:900});await page.goto('/recommend')
  await page.getByRole('button',{name:/^了解/}).first().click();await settle(page,'.destination-detail-layer')
  const orb=page.getByRole('button',{name:'打开详情对话',exact:true}),before=(await orb.boundingBox())!
  const client=await page.context().newCDPSession(page);await client.send('Emulation.setTouchEmulationEnabled',{enabled:true})
  const scrollBefore=await page.evaluate(()=>scrollY)
  await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:before.x+26,y:before.y+26}]})
  await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:before.x-100,y:before.y-100}]})
  await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]})
  const after=(await orb.boundingBox())!;expect(after.x).toBeLessThan(before.x-80);expect(after.y).toBeLessThan(before.y-80)
  await expect(orb).toHaveAttribute('aria-expanded','false');expect(await page.evaluate(()=>scrollY)).toBe(scrollBefore)
  await client.send('Emulation.setTouchEmulationEnabled',{enabled:false});await client.detach()
})

test('conversation follows viewport corners and stays visible after resize', async ({ page }, info) => {
  await page.setViewportSize({width:1280,height:900});await page.goto('/recommend')
  await page.getByRole('button',{name:/^了解/}).first().click();await settle(page,'.destination-detail-layer')
  const orb=page.getByRole('button',{name:'打开详情对话',exact:true})
  for(const [targetX,targetY] of [[4,4],[1276,896]]) {
    const from=(await orb.boundingBox())!;await page.mouse.move(from.x+26,from.y+26);await page.mouse.down();await page.mouse.move(targetX,targetY,{steps:12});await page.mouse.up()
    const at=(await orb.boundingBox())!;expect(at.x).toBeGreaterThanOrEqual(12);expect(at.y).toBeGreaterThanOrEqual(12);expect(at.x+at.width).toBeLessThanOrEqual(1280);expect(at.y+at.height).toBeLessThanOrEqual(900)
    await expect(orb).toHaveAttribute('aria-expanded','false')
    await orb.click();await settle(page,'.layer-conversation')
    const chat=page.getByRole('region',{name:'详情对话',exact:true}),rect=(await chat.boundingBox())!
    expect(rect.x).toBeGreaterThanOrEqual(0);expect(rect.y).toBeGreaterThanOrEqual(0);expect(rect.x+rect.width).toBeLessThanOrEqual(1280);expect(rect.y+rect.height).toBeLessThanOrEqual(900)
    await page.keyboard.press('Escape');await settle(page,'.layer-conversation')
  }
  await orb.click();await settle(page,'.layer-conversation');await page.setViewportSize({width:390,height:640})
  const chat=page.getByRole('region',{name:'详情对话',exact:true})
  await expect.poll(async()=>{const r=(await chat.boundingBox())!;return r.x>=0&&r.y>=0&&r.x+r.width<=390&&r.y+r.height<=640}).toBe(true)
  await settle(page,'.layer-conversation');await page.screenshot({path:info.outputPath('resized-chat.png')})
})

test.afterEach(async ({ page }, info) => {
  const resources = await page.evaluate(() => performance.getEntriesByType('resource').map(entry => entry.name).filter(name => /\/src\/|\/assets\//.test(name))).catch(() => [])
  const loaded = []
  for (const url of resources.filter(url => /useStudioStage|useLayerExit|app\.css|\/assets\/index-/.test(url))) {
    const response = await page.request.get(url)
    loaded.push({ url, sha256: createHash('sha256').update(await response.body()).digest('hex') })
  }
  mkdirSync(info.outputDir, { recursive: true })
  writeFileSync(info.outputPath('loaded-build.json'), JSON.stringify({ mode: process.env.FRONTEND_PRODUCTION === '1' ? 'production' : 'vite-source', resources, loaded,
    stageSource: createHash('sha256').update(readFileSync('src/features/studio/useStudioStage.ts')).digest('hex') }, null, 2))
  writeFileSync(info.outputPath('history.json'), JSON.stringify(await page.evaluate(() => Reflect.get(window, 'frontendHistoryTrace')).catch(() => []), null, 2))
  writeFileSync(info.outputPath('motion.json'), JSON.stringify(await page.evaluate(() => Reflect.get(window, 'frontendMotionTrace')).catch(() => []), null, 2))
})

async function settle(page: import('@playwright/test').Page, selector: string) {
  await page.locator(selector).evaluate(async node => { await Promise.allSettled(node.getAnimations({ subtree: true }).map(animation => animation.finished)) })
}

for (const width of [1920, 1280, 390]) for (const reduced of [false, true]) {
test(`map close after route travel ${width} reduced=${reduced} must not capture an entire page transition`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 900 })
  await page.emulateMedia({ reducedMotion: reduced ? 'reduce' : 'no-preference' })
  await page.goto('/recommend')
  await settle(page, '.route-content')
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '收藏', exact: true }).click()
  await expect(page).toHaveURL(/\/favorites$/)
  await expect.poll(() => page.evaluate(() => document.getAnimations().filter(a => a instanceof CSSAnimation && a.animationName.startsWith('coastal-route-') && a.playState === 'running').length)).toBe(0)
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '推荐', exact: true }).click()
  await expect(page).toHaveURL(/\/explore$/)
  await page.goto('/recommend')
  await expect(page).toHaveURL(/\/recommend$/)
  await expect.poll(() => page.evaluate(() => document.getAnimations().filter(a => a instanceof CSSAnimation && a.animationName.startsWith('coastal-route-') && a.playState === 'running').length)).toBe(0)
  await page.getByRole('button', { name: /^了解/ }).first().click()
  await settle(page, '.destination-detail-layer')
  await page.getByRole('button', { name: '查看位置', exact: true }).click()
  await settle(page, '.location-backdrop')
  await page.evaluate(() => { (Reflect.get(window, 'frontendMotionTrace') as unknown[]).length = 0 })
  await page.getByRole('button', { name: '关闭地图', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '景点位置' })).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('close-map-route-history.png') })
  const trace = await page.evaluate(() => Reflect.get(window, 'frontendMotionTrace') as { kind: string }[])
  expect(trace.filter(entry => entry.kind === 'native-start')).toHaveLength(0)
  await expect(page.locator('.destination-detail')).toBeVisible()
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('map-close-settled.png') })
  for (const close of ['escape', 'back']) {
    await page.getByRole('button', { name: '查看位置', exact: true }).click()
    await settle(page, '.location-backdrop')
    if (close === 'escape') await page.keyboard.press('Escape')
    else await page.goBack()
    await expect(page.getByRole('dialog', { name: '景点位置' })).toHaveCount(0)
    await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
    await expect(page.locator('.destination-detail')).toBeVisible()
  }
  await page.getByRole('button', { name: /返回地点/ }).click()
  await expect(page.locator('.destination-detail')).toHaveCount(0)
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  const closed = await page.evaluate(() => Reflect.get(window, 'frontendMotionTrace') as { kind: string }[])
  expect(closed.filter(entry => ['native-start', 'route'].includes(entry.kind))).toHaveLength(0)
})
}

for (const width of [1920, 1280, 390]) {
  test(`visual and nested history ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/recommend')
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await settle(page, '.route-content')
    await page.evaluate(() => { document.body.style.minHeight = '1800px'; window.scrollTo(0, 110) })
    await expect(page.locator('.shell-header')).toHaveClass(/is-scrolled/)
    await expect(page.locator('.shell-header-veil')).toHaveCount(0)
    await page.screenshot({ path: info.outputPath('top-after.png') })
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.getByRole('button', { name: /^了解/ }).first().click()
    await settle(page, '.destination-detail-layer')
    await page.getByRole('button', { name: '查看位置', exact: true }).click()
    await expect(page.getByRole('dialog', { name: '景点位置' })).toBeVisible()
    await settle(page, '.location-backdrop')
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog', { name: '景点位置' })).toHaveCount(0)
    await page.screenshot({ path: info.outputPath('map-close.png') })
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await expect(page.locator('.destination-detail')).toBeVisible()
    await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
    await page.goBack()
    await expect(page.locator('.destination-detail')).toHaveCount(0)
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
    await expect(page.locator('.destination-card-open').first()).toBeFocused()
    expect(await page.evaluate(() => document.body.style.overflow)).not.toBe('hidden')
    await page.goForward()
    await expect(page.locator('.destination-detail')).toBeVisible()
    await page.goForward()
    await expect(page.getByRole('dialog', { name: '景点位置' })).toBeVisible()
    // Fast Back twice must unwind two layers without starting a query animation.
    await page.goBack()
    await page.goBack()
    await expect(page.locator('.destination-detail')).toHaveCount(0)
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
    expect(await page.evaluate(() => document.body.style.overflow)).not.toBe('hidden')
  })
}

test('account over detail has real pointer and keyboard ownership', async ({ page }) => {
  await page.goto('/recommend')
  await page.getByRole('button', { name: /^了解/ }).first().click()
  await page.getByRole('button', { name: '收藏地点', exact: true }).click()
  const auth = page.getByRole('dialog', { name: '登录 RoamBot' })
  await expect(auth).toBeVisible()
  const input = auth.getByLabel('用户名', { exact: true })
  expect(await input.evaluate(el => {
    const rect = el.getBoundingClientRect()
    return document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2) === el
  })).toBe(true)
  await input.fill('fixture_user')
  await page.keyboard.press('Escape')
  await expect(auth).toHaveCount(0)
  await expect(page.locator('.destination-detail')).toBeVisible()
  await expect(page.getByRole('button', { name: '收藏地点', exact: true })).toBeFocused()
})

test('card action is hit above the full-card detail button', async ({ page }) => {
  await page.goto('/recommend')
  const button = page.locator('.candidate-toggle').first()
  expect(await button.evaluate(el => {
    const r = el.getBoundingClientRect()
    return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)?.closest('.candidate-toggle') === el
  })).toBe(true)
  await button.click()
  await expect(button).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.destination-detail')).toHaveCount(0)
})

for (const width of [1920, 1280, 390]) for (const reduced of [false, true]) {
  test(`card text symbol edge keyboard and team ${width} reduced=${reduced}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: reduced ? 'reduce' : 'no-preference' })
    await page.goto('/recommend')
    await settle(page, '.route-content')
    const button = page.locator('.candidate-toggle').first()
    for (const team of [false, true]) {
      if (team) {
        await page.getByRole('button', { name: '更多功能', exact: true }).click()
        await page.getByRole('button', { name: '发起同行挑选', exact: true }).click()
        await expect(page.getByRole('status').filter({ hasText: '同行挑选中' })).toBeVisible()
      }
      if (await button.getAttribute('aria-pressed') === 'true') await button.click()
      await expect(button).toContainText(team ? '放入同行清单' : '加入比较')
      for (const spot of ['text', 'symbol', 'edge']) {
        const point = await button.evaluate((el, spot) => {
          const b = el.getBoundingClientRect()
          const text = el.firstChild!
          const range = document.createRange()
          const length = text.textContent!.length
          range.setStart(text, spot === 'symbol' ? length - 1 : 0)
          range.setEnd(text, spot === 'symbol' ? length : 4)
          const r = range.getBoundingClientRect()
          const x = spot === 'edge' ? b.x + 2 : r.x + r.width / 2
          const y = spot === 'edge' ? b.y + b.height / 2 : r.y + r.height / 2
          return { x, y, hit: document.elementFromPoint(x, y)?.closest('.candidate-toggle') === el }
        }, spot)
        expect(point.hit).toBe(true)
        const pressed = await button.getAttribute('aria-pressed')
        await page.mouse.click(point.x, point.y)
        await expect(button).toHaveAttribute('aria-pressed', pressed === 'true' ? 'false' : 'true')
        await expect(page.locator('.destination-detail')).toHaveCount(0)
      }
      await button.focus()
      await page.keyboard.press('Space')
      await expect(button).toHaveAttribute('aria-pressed', 'false')
      await page.keyboard.press('Enter')
      await expect(button).toHaveAttribute('aria-pressed', 'true')
      await expect(page.locator('.destination-detail')).toHaveCount(0)
    }
    const title = page.locator('.destination-card h2').first()
    const bounds = (await title.boundingBox())!
    await page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)
    await expect(page.locator('.destination-detail')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('.destination-detail')).toHaveCount(0)
    await page.locator('.destination-card-open').first().focus()
    await page.keyboard.press('Enter')
    await expect(page.locator('.destination-detail')).toBeVisible()
  })
}

test('exit face stays in place and veil clears progressively', async ({ page }, info) => {
  await page.goto('/recommend')
  await page.getByRole('button', { name: /^了解/ }).first().click()
  await settle(page, '.destination-detail-layer')
  const before = (await page.locator('.destination-detail').boundingBox())!
  await page.getByRole('button', { name: /返回地点/ }).click()
  const snapshot = page.locator('[data-exit-snapshot]')
  await expect(snapshot).toHaveCount(1)
  await snapshot.evaluate(node => { for (const animation of node.getAnimations({ subtree: true })) { animation.pause(); animation.currentTime = 160 } })
  const middle = await snapshot.locator('.destination-detail').boundingBox()
  for (const key of ['x', 'y', 'width', 'height'] as const) expect(Math.abs(before[key] - middle![key])).toBeLessThan(2)
  const blur = await snapshot.evaluate(node => Number(getComputedStyle(node).backdropFilter.match(/blur\(([^p]+)/)?.[1]))
  expect(blur).toBeGreaterThan(0)
  expect(blur).toBeLessThan(6)
  await page.screenshot({ path: info.outputPath('exit-mid.png') })
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await snapshot.evaluate(node => { for (const animation of node.getAnimations({ subtree: true })) animation.play() })
  await expect(snapshot).toHaveCount(0)
})

test('stage Back Forward and return loops reuse one result slot', async ({ page }) => {
  await page.goto('/recommend')
  await page.getByRole('button', { name: '← 返回修改' }).click()
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'query')
  const initialLength = await page.evaluate(() => history.length)
  for (let i = 0; i < 3; i++) {
    await page.getByRole('button', { name: '开始推荐', exact: true }).click()
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await page.getByRole('button', { name: '← 返回修改' }).click()
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'query')
  }
  expect(await page.evaluate(() => history.length)).toBe(initialLength)
  // Create a fresh query base to verify the real query -> results Back/Forward pair.
  await page.evaluate(() => { sessionStorage.removeItem('roambot.studio.session.v1'); sessionStorage.removeItem('roambot.session.search-result.v1'); history.replaceState({}, '', location.href) })
  await page.reload()
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await page.goBack()
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'query')
  await page.goForward()
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
})

test('outside click and reduced motion unwind only the top layer and restore scroll', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/recommend')
  await page.evaluate(() => { document.body.style.minHeight = '1800px'; window.scrollTo(0, 80) })
  const before = await page.evaluate(() => window.scrollY)
  await page.getByRole('button', { name: /^了解/ }).first().click()
  expect(await page.locator('.destination-detail-layer').evaluate(node => node.getAnimations({ subtree: true }).filter(animation => animation.playState === 'running').length)).toBe(0)
  await page.getByRole('button', { name: '查看位置', exact: true }).click()
  await page.mouse.click(3, 3)
  await expect(page.getByRole('dialog', { name: '景点位置' })).toHaveCount(0)
  await expect(page.locator('.destination-detail')).toBeVisible()
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
  await page.mouse.click(3, 3)
  await expect(page.locator('.destination-detail')).toHaveCount(0)
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  expect(await page.evaluate(() => window.scrollY)).toBe(before)
  expect(await page.evaluate(() => document.body.style.overflow)).not.toBe('hidden')
})

test('menu exit finishes before the query return slide starts', async ({ page }) => {
  await page.goto('/recommend')
  await page.getByRole('button', { name: '更多功能', exact: true }).click()
  await settle(page, '.studio-overlay-backdrop')
  await page.getByRole('button', { name: '重新开始', exact: true }).click()
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(1)
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'query')
  const slides = await page.evaluate(() => (Reflect.get(window, 'frontendHistoryTrace') as { method: string; phase?: string; exits?: number }[]).filter(entry => entry.method === 'render' && entry.phase === 'toQuery'))
  expect(slides.length).toBeGreaterThan(0)
  expect(slides.every(entry => entry.exits === 0)).toBe(true)
})

test('native links and browser route Back do not replay a second slide', async ({ page }) => {
  await page.goto('/recommend')
  await settle(page, '.route-content')
  await page.evaluate(() => {
    document.querySelector('.coastal-backdrop')?.setAttribute('data-identity', 'same')
    document.querySelector('.shell-header')?.setAttribute('data-identity', 'same')
    const motion = Reflect.get(window, 'frontendMotionTrace') as unknown[]
    motion.length = 0
  })
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '收藏', exact: true }).click()
  await expect(page).toHaveURL(/\/favorites$/)
  await expect.poll(() => page.evaluate(() => (Reflect.get(window, 'frontendMotionTrace') as { kind: string }[]).filter(entry => entry.kind === 'native-finish').length)).toBe(1)
  expect(await page.evaluate(() => (Reflect.get(window, 'frontendMotionTrace') as { kind: string }[]).filter(entry => entry.kind === 'route').length)).toBe(0)
  await page.goBack()
  await expect(page).toHaveURL(/\/recommend$/)
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await expect(page.locator('.coastal-backdrop')).toHaveAttribute('data-identity', 'same')
  await expect(page.locator('.shell-header')).toHaveAttribute('data-identity', 'same')
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
})

test('rapid close cannot skip from map through detail into query', async ({ page }) => {
  await page.goto('/recommend')
  await page.getByRole('button', { name: /^了解/ }).first().click()
  await page.getByRole('button', { name: '查看位置', exact: true }).click()
  await settle(page, '.location-backdrop')
  const button = page.getByRole('button', { name: '关闭地图', exact: true })
  const rect = (await button.boundingBox())!
  const before = await page.evaluate(() => history.length)
  await page.mouse.click(rect.x + rect.width / 2, rect.y + rect.height / 2, { clickCount: 2, delay: 0 })
  await expect(page.getByRole('dialog', { name: '景点位置' })).toHaveCount(0)
  await expect(page.locator('.destination-detail')).toBeVisible()
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  expect(await page.evaluate(() => history.length)).toBe(before)
})

test('programmatic navigation gets one entrance and respects reduced motion', async ({ page }) => {
  await page.route('**/api/v1/auth/login', route => fulfillApiFixture(route, { json: { user: { username: 'fixture_user' }, csrf_token: 'synthetic-test-only' } }))
  await page.goto('/')
  await page.getByRole('button', { name: '同行计划', exact: true }).click()
  await page.getByLabel('用户名', { exact: true }).fill('fixture_user')
  await page.getByLabel('密码', { exact: true }).fill('synthetic-password')
  await page.getByRole('dialog', { name: '登录 RoamBot' }).getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/plans$/)
  await settle(page, '.route-content')
  expect(await page.evaluate(() => (Reflect.get(window, 'frontendMotionTrace') as { kind: string }[]).filter(entry => entry.kind === 'route').length)).toBe(1)
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '推荐', exact: true }).click()
  await expect(page).toHaveURL(/\/explore$/)
  await page.goto('/recommend')
  await expect(page).toHaveURL(/\/recommend$/)
  expect(await page.locator('.route-content').evaluate(node => node.getAnimations().filter(animation => animation.playState === 'running').length)).toBe(0)
})

test('account owns input above a map and returns to that map', async ({ page }) => {
  await page.goto('/recommend')
  await page.getByRole('button', { name: /^了解/ }).first().click()
  await page.getByRole('button', { name: '查看位置', exact: true }).click()
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('roambot:request-account-dialog')))
  const auth = page.getByRole('dialog', { name: '登录 RoamBot' })
  await settle(page, '.auth-dialog')
  const input = auth.getByLabel('用户名', { exact: true })
  expect(await input.evaluate(el => { const r = el.getBoundingClientRect(); return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === el })).toBe(true)
  await input.fill('fixture_user')
  await page.keyboard.press('Escape')
  await expect(auth).toHaveCount(0)
  await expect(page.getByRole('dialog', { name: '景点位置' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: '景点位置' })).toHaveCount(0)
  await expect(page.locator('.destination-detail')).toBeVisible()
})

test('account reaches the browser top layer above an existing native modal', async ({ page }) => {
  await page.goto('/recommend')
  await page.evaluate(() => {
    const native = document.createElement('dialog')
    native.id = 'fixture-native-modal'
    native.innerHTML = '<button>Underlying native fixture</button>'
    document.body.append(native)
    native.showModal()
    window.dispatchEvent(new CustomEvent('roambot:request-account-dialog'))
  })
  const auth = page.getByRole('dialog', { name: '登录 RoamBot' })
  await settle(page, '.auth-dialog')
  const input = auth.getByLabel('用户名', { exact: true })
  expect(await input.evaluate(el => { const r = el.getBoundingClientRect(); return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === el })).toBe(true)
  await input.fill('fixture_user')
  await auth.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(auth).toHaveCount(0)
  expect(await page.locator('#fixture-native-modal').evaluate(el => (el as HTMLDialogElement).open)).toBe(true)
  await page.evaluate(() => { const native = document.querySelector<HTMLDialogElement>('#fixture-native-modal')!; native.close(); native.remove() })
})

test('history toolbar exits in place on desktop and mobile', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => fulfillApiFixture(route, { json: { user: { username: 'fixture_user' }, csrf_token: 'synthetic-test-only' } }))
  await page.route('**/api/v1/history', route => fulfillApiFixture(route, { json: { histories: [{ id: 'fixture-history', mode: 'recommendation', city: '苏州',
    start_date: chinaDate(1), end_date: chinaDate(1), item_count: 4, created_at: '2026-10-13T08:00:00Z' }] } }))
  await page.goto('/history')
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.getByRole('button', { name: '更多历史操作' }).click()
    await settle(page, '.history-menu-popover')
    const before = (await page.getByRole('toolbar', { name: '历史快捷操作' }).boundingBox())!
    await page.getByRole('button', { name: '收起历史操作' }).click()
    await expect(page.getByRole('toolbar', { name: '历史快捷操作' })).toHaveCount(0)
    const snapshot = page.locator('[data-exit-snapshot].history-menu-popover')
    await expect(snapshot).toHaveCount(1)
    await snapshot.evaluate(node => { for (const animation of node.getAnimations()) { animation.pause(); animation.currentTime = 140 } })
    const middle = (await snapshot.boundingBox())!
    for (const key of ['x', 'y', 'width', 'height'] as const) expect(Math.abs(before[key] - middle[key])).toBeLessThan(2)
    await snapshot.evaluate(node => { for (const animation of node.getAnimations()) animation.play() })
    await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '更多历史操作' })).toBeFocused()
  }
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('button', { name: '更多历史操作' }).click()
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
})

test('native create-plan dialog exits in place and restores the results layer', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => fulfillApiFixture(route, { json: { user: { username: 'fixture_user' }, csrf_token: 'synthetic-test-only' } }))
  await page.goto('/recommend')
  await page.getByRole('button', { name: '更多功能', exact: true }).click()
  await page.getByRole('button', { name: '发起同行挑选', exact: true }).click()
  await page.locator('.candidate-toggle').nth(0).click()
  await page.locator('.candidate-toggle').nth(1).click()
  await page.getByRole('button', { name: '发起同行计划', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '创建同行计划', exact: true })
  await expect(dialog).toBeVisible()
  await settle(page, '.plan-create-dialog')
  const before = (await dialog.boundingBox())!
  await page.keyboard.press('Escape')
  await dialog.evaluate(node => { for (const animation of node.getAnimations({ subtree: true })) { animation.pause(); animation.currentTime = 140 } })
  const middle = (await dialog.boundingBox())!
  for (const key of ['x', 'y', 'width', 'height'] as const) expect(Math.abs(before[key] - middle[key])).toBeLessThan(2)
  await dialog.evaluate(node => { for (const animation of node.getAnimations({ subtree: true })) animation.play() })
  await expect(dialog).toHaveCount(0)
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await expect(page.getByRole('button', { name: '发起同行计划', exact: true })).toBeFocused()
})

for (const width of [1920, 1280, 390]) for (const reduced of [false, true]) {
  test(`T16 edit results in place ${width} reduced=${reduced}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: reduced ? 'reduce' : 'no-preference' })
    let requests = 0
    let submitted: Record<string, unknown> | null = null
    await page.route('**/api/v1/recommendations', route => {
      requests++; submitted = route.request().postDataJSON()
      const result = structuredClone(studioResponse)
      result.items[0].destination.name = '更新后的金鸡湖'
      return fulfillApiFixture(route, { json: result })
    })
    await page.goto('/recommend')
    await settle(page, '.route-content')
    await page.evaluate(() => {
      const saved = JSON.parse(sessionStorage.getItem('roambot.studio.session.v1')!)
      saved.draft.companions = ['南京站']; saved.draft.companionOriginCoordinates = [null]
      sessionStorage.setItem('roambot.studio.session.v1', JSON.stringify(saved))
    })
    await page.reload()
    await settle(page, '.route-content')
    const original = await page.evaluate(() => ({ state: history.state, length: history.length }))
    const range = page.getByRole('button', { name: /编辑目的地范围/ })
    await range.click()
    await page.getByRole('dialog', { name: '目的地范围', exact: true }).getByLabel('最大距离（km）').fill('120')
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog', { name: '目的地范围' })).toHaveCount(0)
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await expect(range).toContainText('50 km')
    await range.click()
    await page.getByRole('dialog', { name: '目的地范围', exact: true }).getByLabel('最大距离（km）').fill('120')
    await page.getByRole('button', { name: '保存条件' }).click()
    await expect(page.getByRole('button', { name: '更新推荐', exact: true })).toBeVisible()
    await expect(page.locator('.destination-card h2').first()).toHaveText('金鸡湖景区')
    expect(requests).toBe(0)
    expect(await page.evaluate(() => ({ state: history.state, length: history.length }))).toEqual(original)
    // Dirty results also stay in their explicit stage after a real refresh.
    await page.reload()
    await settle(page, '.route-content')
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await expect(page.getByRole('button', { name: '更新推荐', exact: true })).toBeVisible()
    const other = page.getByRole('button', { name: /编辑其他偏好/ })
    await other.click()
    await page.getByRole('button', { name: /同行出发地/ }).click()
    await expect(page.getByRole('dialog', { name: '同行出发地' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await other.click()
    await page.getByRole('button', { name: /同行出发地/ }).click()
    await page.getByRole('combobox', { name: '同行人 1 出发地' }).fill('无锡站')
    await page.getByRole('button', { name: '保存条件' }).click()
    expect(requests).toBe(0)
    expect(await page.evaluate(() => ({ state: history.state, length: history.length }))).toEqual(original)
    await page.getByRole('button', { name: '更新推荐', exact: true }).click()
    await expect(page.locator('.destination-card h2').first()).toHaveText('更新后的金鸡湖')
    expect(requests).toBe(1)
    expect(submitted).toMatchObject({ max_distance_km: 120, companion_origins: ['无锡站'] })
    await expect(page.getByRole('button', { name: '更新推荐', exact: true })).toHaveCount(0)
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    await page.getByRole('button', { name: /^了解/ }).first().click()
    await page.getByRole('button', { name: '查看位置', exact: true }).click()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog', { name: '景点位置' })).toHaveCount(0)
    await page.keyboard.press('Escape')
    await expect(page.locator('.destination-detail')).toHaveCount(0)
    await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    const trace = await page.evaluate(() => Reflect.get(window, 'frontendHistoryTrace') as { method: string; phase?: string }[])
    expect(trace.filter(entry => entry.method === 'render' && ['query', 'toQuery'].includes(entry.phase ?? ''))).toHaveLength(0)
  })
}
