import { installLegacyAssistantFixture } from './helpers'
import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => { await installLegacyAssistantFixture(page) })

test('manual entry is available on an empty workspace', async ({ page }) => {
  await page.goto('/recommend')
  await page.getByRole('button', { name: '更多功能' }).click()
  await page.getByRole('button', { name: '手动填写条件' }).click()
  await page.getByRole('button', { name: '出发地', exact: true }).click()
  await page.getByRole('combobox', { name: '主出发地' }).fill('苏州站')
  await page.getByRole('button', { name: '保存条件' }).click()
  await expect(page.getByRole('button', { name: /编辑出发地/ })).toContainText('苏州站')
  await page.getByRole('button', { name: '更多功能' }).click()
  await page.getByRole('button', { name: '手动填写条件' }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('expired assistant session requests login and preserves unsent text', async ({ page }) => {
  await page.route('**/api/v1/assistant/turns', route => route.fulfill({
    status: 401, contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'authentication_required', message: 'Authentication is required.', fields: [] } }),
  }))
  await page.goto('/recommend')
  const composer = page.getByRole('textbox', { name: '继续补充条件' })
  await composer.fill('苏州10月11日')
  await page.getByRole('button', { name: '发送消息' }).click()
  await expect(page.getByRole('dialog', { name: '登录 RoamBot' })).toBeVisible()
  await expect(composer).toHaveValue('苏州10月11日')
  await expect(page.getByText(/AI暂不可用/)).toHaveCount(0)
})
