import { expect, test, type Page } from '@playwright/test'

// Running the normal suite never spends real provider quotas.
test.skip(process.env.ROAMBOT_RUN_LIVE_BROWSER !== '1', 'Explicit real-provider authorization required')

async function say(page: Page, message: string, required: string) {
  await page.keyboard.press('Alt+/')
  await expect.poll(() => page.evaluate(() => document.activeElement?.hasAttribute('data-command-input'))).toBe(true)
  await page.keyboard.insertText(message)
  const planned = page.waitForResponse(response => response.url().endsWith('/assistant/commands/proposals'))
  const executed = page.waitForResponse(response => response.url().endsWith('/assistant/commands/execute'))
  await page.keyboard.press('Enter')
  const response = await planned
  expect(response.ok(), await response.text()).toBeTruthy()
  const proposal = await response.json()
  expect(proposal.question).toBeNull()
  expect(proposal.actions.map((action: { tool: string }) => action.tool)).toContain(required)
  const result = await executed
  expect(result.ok(), await result.text()).toBeTruthy()
  expect((await result.json()).status).toBe('completed')
  await expect(page.locator('.studio-composer[data-busy="true"]:visible')).toHaveCount(0)
}

test('real model handles independent keyboard intents without a prescribed recommendation flow', async ({ page }, info) => {
  test.setTimeout(90000)
  await page.addInitScript(() => {
    Object.assign(window, { pointerInputs: 0 })
    document.addEventListener('pointerdown', () => {
      const state = window as Window & { pointerInputs: number }; state.pointerInputs++
    }, true)
  })
  await page.goto('/')
  await say(page, '我暂时不查景点，先告诉我在这里可以做哪些操作', 'describe_capabilities')
  await expect(page.getByText(/可以直接修改条件并查询/)).toBeVisible()
  await say(page, '带我去推荐页，展开更多功能让我看看', 'show_tools')
  await expect(page.getByRole('dialog', { name: '更多功能' })).toBeVisible()
  await say(page, '把刚展开的功能窗口关掉', 'close_layer')
  await expect(page.getByRole('dialog', { name: '更多功能' })).toHaveCount(0)
  await say(page, '我要创建账号，打开注册表单', 'open_account')
  await expect(page.getByRole('heading', { name: '创建账户' })).toBeVisible()
  expect(await page.evaluate(() => (window as Window & { pointerInputs: number }).pointerInputs)).toBe(0)
  await page.screenshot({ path: info.outputPath('real-model-keyboard.png') })
})
