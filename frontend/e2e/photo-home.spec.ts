import { openCondition } from './helpers'
import { expect, test, type Page } from '@playwright/test'

async function fixtureSession(page: Page, username?: string) {
  let account = username
  await page.route('**/api/v1/auth/**', async route => {
    const endpoint = new URL(route.request().url()).pathname
    if (endpoint.endsWith('/logout')) {
      account = undefined
      return route.fulfill({ status: 204 })
    }
    if (endpoint.endsWith('/login') || endpoint.endsWith('/register')) account = route.request().postDataJSON().username
    return route.fulfill({ status: account ? 200 : 401, json: account
      ? { user: { id: 'fixture-owner', username: account }, csrf_token: 'fixture-only' }
      : { error: { code: 'unauthorized', message: '请登录', fields: [] } } })
  })
}

test('photo remains full bleed with a non-interactive contrast layer', async ({ page }, info) => {
  await fixtureSession(page)
  await page.goto('/')
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible()
  for (const selector of ['.home-shade']) {
    await expect(page.locator(selector)).toBeVisible()
    await expect(page.locator(selector)).toHaveCSS('pointer-events', 'none')
  }
  await expect(page.locator('.home-photo')).toHaveJSProperty('complete', true)
  await page.screenshot({ path: `../test-results/home-clear-${info.project.name}.png` })
})

test('photo home keeps both rows aligned before and after login', async ({ page }, info) => {
  await fixtureSession(page)
  await page.goto('/')
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible()
  await expect(page.locator('.home-header')).toHaveCount(1)
  await expect(page.locator('.primary-nav')).toHaveCount(0)
  await expect(page.locator('.home-photo')).toHaveJSProperty('complete', true)
  const first = await page.locator('.home-brand').boundingBox()
  const second = await page.locator('.home-actions').boundingBox()
  const start = await page.locator('.home-start').boundingBox()
  expect(start?.height).toBe(58)
  expect((await page.locator('.home-scene').boundingBox())?.width).toBe(page.viewportSize()?.width)
  if (info.project.name.startsWith('mobile')) {
    const text = await page.locator('.home-start > span').boundingBox()
    expect(Math.abs(text!.x + text!.width / 2 - start!.x - start!.width / 2)).toBeLessThan(1)
  }
  await page.screenshot({ path: `../test-results/photo-home-${info.project.name}-guest.png` })
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('dialog', { name: '登录 RoamBot', exact: true }).getByLabel('用户名', { exact: true }).fill('photo_fixture')
  await page.getByRole('dialog', { name: '登录 RoamBot', exact: true }).getByLabel('密码', { exact: true }).fill('FixturePassword123!')
  await page.getByRole('dialog').getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('link', { name: '收藏', exact: true })).toBeVisible()
  await expect(page).toHaveURL(/\/$/)
  expect((await page.locator('.home-brand').boundingBox())?.y).toBe(first?.y)
  expect((await page.locator('.home-actions').boundingBox())?.y).toBe(second?.y)
  await page.screenshot({ path: `../test-results/photo-home-${info.project.name}-logged.png` })
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page.getByRole('button', { name: '注册', exact: true })).toBeVisible()
})

test('exploration entry and the separate legacy query retain their own navigation and draft', async ({ page }, info) => {
  await fixtureSession(page)
  await page.goto('/')
  await page.getByRole('link', { name: '开始探索' }).click()
  await expect(page).toHaveURL(/\/explore$/)
  if (info.project.name.startsWith('mobile')) await page.setViewportSize({ width: 320, height: 700 })
  const home = await page.getByRole('link', { name: '首页', exact: true }).boundingBox()
  const brand = await page.getByRole('link', { name: 'RoamBot', exact: true }).boundingBox()
  const account = await page.getByRole('button', { name: '账户', exact: true }).boundingBox()
  expect(home!.x).toBeGreaterThanOrEqual(brand!.x + brand!.width)
  expect(home!.x + home!.width).toBeLessThanOrEqual(account!.x)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize()!.width)
  await page.screenshot({ path: `../test-results/home-entry-${info.project.name}.png` })
  await page.goto('/recommend')
  await openCondition(page, '出发地')
  await page.getByLabel('主出发地', { exact: true }).fill('苏州站')
  await page.getByRole('button', { name: '保存条件' }).click()
  await page.reload()
  await expect(page.getByRole('region', { name: '当前出行条件' })).toContainText('苏州站')
  await page.getByRole('link', { name: '首页', exact: true }).click()
  await expect(page.locator('.home-scene')).toBeVisible()
  await page.getByRole('link', { name: '开始探索' }).click()
  await expect(page).toHaveURL(/\/explore$/)
  await page.goto('/recommend')
  await expect(page.getByRole('region', { name: '当前出行条件' })).toContainText('苏州站')
})

test('registration opens directly and guest plans continue to plans after authentication', async ({ page }) => {
  await fixtureSession(page)
  await page.goto('/')
  await page.getByRole('button', { name: '注册', exact: true }).click()
  await expect(page.getByRole('button', { name: '注册并登录' })).toBeVisible()
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('button', { name: '同行计划', exact: true }).click()
  await page.getByRole('dialog', { name: '登录 RoamBot', exact: true }).getByLabel('用户名', { exact: true }).fill('plan_fixture')
  await page.getByRole('dialog', { name: '登录 RoamBot', exact: true }).getByLabel('密码', { exact: true }).fill('FixturePassword123!')
  await page.getByRole('dialog').getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/plans$/)
})

test('narrow screens contain long account names without horizontal overflow', async ({ page }) => {
  await fixtureSession(page, '很长的账户名称'.repeat(8))
  await page.setViewportSize({ width: 320, height: 568 })
  await page.goto('/')
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320)
  const row = await page.locator('.home-account-state').boundingBox()
  expect(row!.x + row!.width).toBeLessThanOrEqual(320)
})

test('desktop entry hover gives movement feedback without underline and place label stays subtle', async ({ page }, info) => {
  await fixtureSession(page)
  await page.goto('/')
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible()
  const prefix = page.locator('.home-location > span')
  if (info.project.name.startsWith('mobile')) {
    await expect(prefix).toBeVisible()
    return
  }
  await expect(prefix).toBeHidden()
  for (const selector of ['.home-guest-account button:first-child', '.home-guest-account button:last-child', '.home-plan']) {
    const control = page.locator(selector)
    await control.hover()
    await expect.poll(() => control.evaluate(el => getComputedStyle(el).transform)).toBe('matrix(1, 0, 0, 1, 0, -1)')
    expect(await control.evaluate(el => getComputedStyle(el).textDecorationLine)).toBe('none')
  }
  await page.locator('.home-start').hover()
  await expect.poll(() => page.locator('.home-start').evaluate(el => getComputedStyle(el).transform)).toBe('matrix(1, 0, 0, 1, 0, -2)')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('dialog', { name: '登录 RoamBot', exact: true }).getByLabel('用户名', { exact: true }).fill('hover_fixture')
  await page.getByRole('dialog', { name: '登录 RoamBot', exact: true }).getByLabel('密码', { exact: true }).fill('FixturePassword123!')
  await page.getByRole('dialog').getByRole('button', { name: '登录', exact: true }).click()
  for (const label of ['收藏', '历史', '同行计划']) {
    const control = page.getByRole('link', { name: label, exact: true })
    await control.hover()
    await expect.poll(() => control.evaluate(el => getComputedStyle(el).transform)).toBe('matrix(1, 0, 0, 1, 0, -1)')
    expect(await control.evaluate(el => getComputedStyle(el).textDecorationLine)).toBe('none')
  }
})

test('delayed sessions reserve rows and failed logout keeps the account with reduced motion', async ({ page }) => {
  let releaseSession!: () => void
  const sessionReady = new Promise<void>(resolve => { releaseSession = resolve })
  let releaseLogout!: () => void
  const logoutReady = new Promise<void>(resolve => { releaseLogout = resolve })
  let logoutCalls = 0
  await page.route('**/api/v1/auth/me', async route => {
    await sessionReady
    await route.fulfill({ json: { user: { id: 'fixture', username: 'steady_fixture' }, csrf_token: 'fixture-only' } })
  })
  await page.route('**/api/v1/auth/logout', async route => {
    logoutCalls++
    await logoutReady
    await route.fulfill({ status: 500, json: { error: { code: 'fixture_error', message: 'Fixture failure' } } })
  })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 375, height: 500 })
  await page.goto('/')
  await expect(page.locator('.home-session-placeholder')).toBeVisible()
  await expect(page.getByRole('button', { name: '登录', exact: true })).toHaveCount(0)
  const before = await page.locator('.home-brand').boundingBox()
  releaseSession()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
  expect((await page.locator('.home-brand').boundingBox())?.y).toBe(before?.y)
  expect(await page.locator('.home-start').evaluate(el => getComputedStyle(el).transitionDuration)).toBe('0s')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(375)
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page.getByRole('button', { name: '退出登录' })).toBeDisabled()
  releaseLogout()
  await expect(page.getByRole('alert')).toHaveText('退出失败，请稍后重试。')
  await expect(page.locator('.home-username')).toHaveText('steady_fixture')
  expect(logoutCalls).toBe(1)
})
