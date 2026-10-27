import { expect, test, type Page } from '@playwright/test'

let lastCommandAt = 0
async function command(page: Page, message: string, confirm = false) {
  const wait = Math.max(0, 8000 - (Date.now() - lastCommandAt))
  if (wait) await page.waitForTimeout(wait)
  lastCommandAt = Date.now()
  console.info('command:', message)
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
  await expect(page.locator('.studio-composer[data-busy="true"]:visible')).toHaveCount(0)
  await page.keyboard.press('Alt+/')
  await expect.poll(() => page.evaluate(() => document.activeElement?.hasAttribute('data-command-input'))).toBe(true)
  await page.keyboard.press('ControlOrMeta+A')
  await page.keyboard.insertText(message)
  const planning = page.waitForResponse(r => r.url().endsWith('/assistant/commands/proposals'), { timeout: 15000 })
  const execution = page.waitForResponse(r => r.url().endsWith('/assistant/commands/execute'), { timeout: 15000 })
  await page.keyboard.press('Enter')
  const response = await planning
  expect(response.ok(), await response.text()).toBeTruthy()
  const proposal = await response.json()
  expect(proposal.question).toBeNull()
  if (confirm) {
    expect(proposal.requires_confirmation).toBe(true)
    await page.keyboard.press('Alt+/')
    await expect(page.getByRole('textbox', { name: '确认操作指令' })).toBeFocused()
    await page.keyboard.insertText('确认')
    await page.keyboard.press('Enter')
  }
  const executed = await execution
  expect(executed.ok(), await executed.text()).toBeTruthy()
  const result = await executed.json()
  expect(result.status, JSON.stringify(result)).toBe('completed')
  await expect(page.locator('.studio-composer[data-busy="true"]:visible')).toHaveCount(0)
  return result
}

test('uses chat and keyboard without pointer input from an empty session', async ({ page, context }, info) => {
  test.setTimeout(300000)
  await page.addInitScript(() => {
    Object.assign(window, { pointerInputs: 0 })
    document.addEventListener('pointerdown', () => {
      const state = window as Window & { pointerInputs: number }; state.pointerInputs++
    }, true)
  })
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.goto('/')
  // The home entry now leads to live discovery. Enter the business workspace
  // through its real home link, using only keyboard input; discovery intake
  // handoff is covered independently in discovery.spec.ts.
  const plansLink = page.getByRole('link', { name: '行程中心', exact: true })
  for (let i = 0; i < 12 && !await plansLink.evaluate(node => node === document.activeElement); i++)
    await page.keyboard.press('Tab')
  await expect(plansLink).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/itineraries$/)
  await expect(page.getByRole('button', { name: '打开操作助手', exact: true })).toBeVisible()
  await command(page, '能做什么')
  await expect(page.getByText(/可以直接修改条件并查询/)).toBeVisible()
  await command(page, '打开注册')
  await expect(page.getByRole('heading', { name: '创建账户' })).toBeVisible()
  // Credentials stay in the native secure form. Reach it using Tab, never a pointer.
  const username = page.getByRole('textbox', { name: '用户名' })
  for (let i = 0; i < 8 && !await username.evaluate(input => input === document.activeElement); i++)
    await page.keyboard.press('Tab')
  await expect(username).toBeFocused()
  await page.keyboard.insertText('key_' + crypto.randomUUID().replaceAll('-', '').slice(0, 10))
  await page.keyboard.press('Tab')
  // Registration mode has no password-help button between username and password.
  await expect(page.getByLabel('密码', { exact: true })).toBeFocused()
  await page.keyboard.insertText('isolated-keyboard-fixture-password')
  const registration = page.waitForResponse(r => r.url().endsWith('/auth/register'))
  await page.keyboard.press('Enter')
  expect((await registration).status()).toBe(201)
  await expect(page.getByRole('dialog', { name: '登录 RoamBot' })).toHaveCount(0)

  await command(page, '打开更多功能')
  await expect(page.getByRole('dialog', { name: '更多功能' })).toBeVisible()
  await command(page, '返回')
  await expect(page.getByRole('dialog', { name: '更多功能' })).toHaveCount(0)
  await command(page, '苏州站出发，明天一天，500公里内，湖景、公园、博物馆或古镇')
  await command(page, '开始推荐')
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await command(page, '向下看')
  await expect.poll(() => page.evaluate(() => scrollY)).toBeGreaterThan(0)
  await command(page, '回到顶部')
  await expect.poll(() => page.evaluate(() => scrollY)).toBe(0)
  await command(page, '收藏第二个')
  await command(page, '选中前两个')
  await command(page, '查看第一个地点')
  await command(page, '查看位置')
  await expect(page.locator('.location-backdrop:not([data-exit-snapshot])')).toBeVisible()
  await command(page, '返回')
  await expect(page.locator('.location-backdrop:not([data-exit-snapshot])')).toHaveCount(0)
  await command(page, '返回')
  await expect(page.locator('[data-detail-id]:not([data-exit-snapshot])')).toHaveCount(0)
  // Depart from the main recommendation flow and come back via chat.
  await command(page, '查看收藏')
  await command(page, '查看第一个地点')
  await expect(page.getByRole('dialog')).toBeVisible()
  await command(page, '返回')
  await command(page, '发起同行挑选')
  await expect(page.locator('.studio-team-mode')).toBeVisible()
  await command(page, '就这两个，建个计划')
  await expect(page).toHaveURL(/\/plans\/[^/]+$/)
  await command(page, '生成邀请', true)
  const plans = (await (await context.request.get('/api/v1/plans')).json()).plans
  expect(plans).toHaveLength(1)
  expect((await (await context.request.get('/api/v1/favorites')).json()).favorites).toHaveLength(1)
  expect(await page.evaluate(() => (window as Window & { pointerInputs: number }).pointerInputs)).toBe(0)
  expect(errors).toEqual([])
  await page.screenshot({ path: info.outputPath('keyboard-only.png'), fullPage: true })
})
