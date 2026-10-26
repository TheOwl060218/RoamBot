import { expect, test } from '@playwright/test'

test('content-sized plan capsule and history toolbar stay usable at both viewport sizes', async ({ page }, info) => {
  let destination = '金鸡湖'
  // UI fixtures intercept every API request: never read or write the user's running database.
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    const plan = { id: 'capsule-fixture', city: '苏州', name: '演示计划', start_date: '2026-12-01', end_date: '2026-12-02',
      created_at: '2026-10-06T00:00:00Z', status: 'decided', ended: false, final_candidate_id: 'a',
      candidates: [{ id: 'a', snapshot: { destination: { name: destination } } }], expected_count: 2, summary: { voted_count: 2 } }
    const body = url.pathname.endsWith('/auth/me') ? { user: { username: 'fixture' }, csrf_token: 'fixture' }
      : url.pathname.endsWith('/plans') ? { plans: [plan] }
      : url.pathname.endsWith('/history') ? { histories: [{ id: 'history-fixture', mode: 'recommendation', city: '苏州', start_date: '2026-12-01', end_date: '2026-12-02', created_at: '2026-10-06T00:00:00Z', item_count: 2 }] }
      : url.pathname.endsWith('/share') ? { share: { id: 'share-fixture', url: '/share/fixture' } }
      : { favorites: [] }
    await route.fulfill({ json: body })
  })
  await page.goto('/history')
  const status = page.locator('.primary-nav .plan-status-link')
  await expect(status).toBeVisible()
  if (info.project.name.startsWith('desktop')) {
    await status.hover()
    await expect(status).toContainText('金鸡湖')
    await expect.poll(async () => (await status.boundingBox())!.width).toBeLessThan(320)
    const shortRight = (await status.boundingBox())!.x + (await status.boundingBox())!.width
    destination = '苏州金鸡湖文化旅游景区'
    await page.evaluate(() => window.dispatchEvent(new Event('roambot.plan-changed')))
    await expect(status).toContainText(destination)
    await expect(status).toHaveAttribute('title', new RegExp(destination))
    expect(Math.abs((await status.boundingBox())!.x + (await status.boundingBox())!.width - shortRight)).toBeLessThan(1)
    expect((await status.boundingBox())!.width).toBeLessThanOrEqual(340)
  }
  await page.getByRole('button', { name: '更多历史操作' }).click()
  const toolbar = page.getByRole('toolbar', { name: '历史快捷操作' })
  await expect(toolbar).toBeVisible()
  await expect(page.getByRole('button', { name: '删除历史' })).toHaveCount(0)
  const bounds = (await toolbar.boundingBox())!
  expect(bounds.x).toBeGreaterThanOrEqual(0)
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  await page.getByRole('button', { name: '更多操作' }).click()
  await expect(page.getByRole('button', { name: '删除历史' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(toolbar).toBeHidden()
  await expect(page.getByRole('button', { name: '更多历史操作' })).toBeFocused()
  await page.getByRole('button', { name: '更多历史操作' }).click()
  await page.getByRole('button', { name: '创建分享' }).click()
  // Keep the new link available immediately for copying or revocation.
  await expect(toolbar).toBeVisible()
  await expect(page.getByRole('button', { name: '复制分享链接' })).toBeVisible()
  await expect(page.getByRole('button', { name: '撤销分享' })).toBeVisible()
  const sharedBounds = (await toolbar.boundingBox())!
  expect(sharedBounds.x).toBeGreaterThanOrEqual(0)
  expect(sharedBounds.x + sharedBounds.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  await page.getByRole('button', { name: '撤销分享' }).click()
  await expect(page.getByRole('button', { name: '创建分享' })).toBeVisible()
  await page.getByRole('button', { name: '收起历史操作' }).click()
  await expect(toolbar).toBeHidden()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})
