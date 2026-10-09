import { expect, test } from '@playwright/test'

test('pending capsule stays visible at top and disappears on failure', async ({ page }, testInfo) => {
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  let requests = 0
  await page.route('**/api/v1/recommendations', async route => {
    requests++
    await gate
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({
      error: { code: 'unavailable', message: '测试查询失败', fields: [] },
    }) })
  })
  await page.goto('/recommend')
  await page.getByLabel('主出发地', { exact: true }).fill('苏州站')
  await page.getByRole('checkbox', { name: '湖景', exact: true }).check()
  if (testInfo.project.name === 'desktop-chromium') {
    await page.getByRole('button', { name: '临湖', exact: true }).click()
    await expect(page.getByRole('button', { name: '短途近程', exact: true })).toBeDisabled()
  } else {
    await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  }
  const capsule = page.getByRole('status').filter({ hasText: '正在查询推荐地点' })
  await expect(capsule).toBeVisible()
  const box = (await capsule.boundingBox())!
  expect(box.y).toBeGreaterThanOrEqual(0)
  expect(box.y + box.height).toBeLessThan(220)
  expect(box.x).toBeGreaterThanOrEqual(0)
  expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  await page.waitForTimeout(2300)
  await expect(capsule).toBeVisible()
  expect(requests).toBe(1)
  await page.screenshot({ path: `../evidence/search-pending-${testInfo.project.name}-20261009.png` })
  release()
  await expect(capsule).toHaveCount(0)
  await expect(page.getByRole('button', { name: '开始推荐', exact: true })).toBeEnabled()
})
