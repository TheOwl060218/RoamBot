import { installLegacyAssistantFixture } from './helpers'
import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => { await installLegacyAssistantFixture(page) })

for (const failed of [false, true]) test(`${failed ? 'failed' : 'successful'} input stays in a viewport-sized page without body scrolling`, async ({ page }) => {
  await page.route('**/api/v1/assistant/turns', route => route.fulfill(failed ? { status: 503, json: {
    error: { code: 'assistant_unavailable', message: 'unavailable', fields: [] },
  } } : { json: {
    revision: 0, source: 'live', reply: '从苏州出发。', question: '准备哪天出发？', patch: { main_origin: '苏州' },
  } }))
  await page.goto('/recommend')
  const input = page.getByRole('textbox', { name: '继续补充条件' })
  await input.fill('苏州')
  await page.getByRole('button', { name: '发送消息' }).click()
  if (failed) await expect(page.getByText(/AI暂不可用/)).toBeVisible()
  else await expect(page.getByRole('button', { name: /编辑出发地/ })).toContainText('苏州')
  const geometry = await page.evaluate(() => ({
    scroll: window.scrollY, overflow: document.documentElement.scrollHeight - innerHeight,
  }))
  expect(geometry.scroll).toBe(0)
  expect(geometry.overflow).toBeLessThan(2)
  await input.click()
  expect(await page.evaluate(() => window.scrollY)).toBe(0)
})
