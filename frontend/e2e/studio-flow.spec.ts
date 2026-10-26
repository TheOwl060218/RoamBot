import { expect, test } from '@playwright/test'
import { installLegacyAssistantFixture, openCondition, fillStudioConditions } from './helpers'
test.beforeEach(async ({ page }) => { await installLegacyAssistantFixture(page) })

test('Mock conversation progressively patches shared conditions and only explicit query runs', async ({ page }) => {
  let queries = 0
  page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/recommendations')) queries++ })
  await page.goto('/recommend')
  const input = page.getByRole('textbox', { name: '继续补充条件' })
  for (const message of ['苏州站', '明天', '想看湖景']) {
    await input.fill(message); await page.getByRole('button', { name: '发送消息' }).click()
    await expect(input).toHaveValue('')
  }
  await expect(page.getByRole('region', { name: '当前出行条件' })).toContainText('苏州站')
  await expect(page.getByRole('region', { name: '最近对话' })).toContainText('演示助手')
  expect(queries).toBe(0)
  await page.getByRole('button', { name: '开始推荐' }).click()
  await expect(page.getByTestId('destination-card').first()).toBeVisible()
  expect(queries).toBe(1)
  await page.getByRole('button', { name: /^了解/ }).first().click()
  await page.getByRole('button', { name: '打开详情对话' }).click()
  const detailInput = page.getByRole('region', { name: '详情对话', exact: true }).getByRole('textbox', { name: '继续补充条件' })
  await detailInput.fill('路程怎么样'); await page.getByRole('region', { name: '详情对话', exact: true }).getByRole('button', { name: '发送消息' }).click()
  await expect(input).toHaveValue('')
  await expect(page.getByRole('region', { name: '详情对话', exact: true })).toContainText('km')
  expect(queries).toBe(1)
})
test('AI failure retains text and manual search remains independently usable', async ({ page }) => {
  await page.route('**/api/v1/assistant/turns', r => r.fulfill({ status: 503, json: { error: { code: 'assistant_unavailable', message: 'private', fields: [] } } }))
  await page.goto('/recommend')
  const input = page.getByRole('textbox', { name: '继续补充条件' })
  await input.fill('我想安静一点'); await page.getByRole('button', { name: '发送消息' }).click()
  await expect(page.getByText(/AI暂不可用/)).toBeVisible(); await expect(input).toHaveValue('我想安静一点')
  await fillStudioConditions(page); await page.getByRole('button', { name: '开始推荐' }).click()
  await expect(page.getByTestId('destination-card').first()).toBeVisible()
  await expect(input).toHaveValue('我想安静一点')
})
test('late AI patch cannot overwrite manual changes or initiate a query', async ({ page }) => {
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve }); let queries = 0; let started = false; let executions = 0
  page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/recommendations')) queries++; if (r.url().endsWith('/commands/execute')) executions++ })
  await page.route('**/api/v1/assistant/turns', async route => {
    const body = route.request().postDataJSON(); started = true; await gate
    await route.fulfill({ json: { revision: body.revision, patch: { main_origin: '上海站' }, reply: '条件已更新', source: 'demo' } })
  })
  await page.goto('/recommend'); const input = page.getByRole('textbox', { name: '继续补充条件' })
  await input.fill('换到上海站'); await page.getByRole('button', { name: '发送消息' }).click()
  await expect.poll(() => started).toBe(true)
  await openCondition(page, '出发地')
  await page.getByLabel('主出发地', { exact: true }).fill('苏州站'); await page.getByRole('button', { name: '保存条件' }).click()
  release(); await expect(page.getByText(/页面、条件或选择已变化，请重新发起操作/).first()).toBeVisible()
  await expect(page.getByRole('region', { name: '当前出行条件' })).toContainText('苏州站')
  expect(queries).toBe(0)
  expect(executions).toBe(0)
})
test('broken optional storage does not prevent starting an editable session', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('roambot.studio.session.v1', '{"version":1,"draft":{"mode":"broken"}}'))
  await page.goto('/recommend'); await expect(page.getByRole('textbox', { name: '继续补充条件' })).toBeVisible()
  await openCondition(page, '出发地'); await expect(page.getByLabel('主出发地')).toHaveValue('')
})
