import { expect, test } from '@playwright/test'
import { fillStudioConditions } from './helpers'
test('pending capsule remains at top and double clicks cause one query', async ({ page }) => {
  let release!: () => void; const gate = new Promise<void>(resolve => { release = resolve }); let queries = 0
  await page.route('**/api/v1/recommendations', async route => { queries++; await gate; await route.fulfill({ status: 503, json: { error: { code: 'unavailable', message: 'private', fields: [] } } }) })
  await page.goto('/recommend'); await fillStudioConditions(page)
  await page.getByRole('button', { name: '开始推荐' }).dblclick()
  const capsule = page.getByRole('status').filter({ hasText: '正在查询推荐地点' }); await expect(capsule).toBeVisible()
  const b = (await capsule.boundingBox())!; expect(b.y).toBeGreaterThanOrEqual(0); expect(b.y + b.height).toBeLessThan(220); expect(b.x).toBeGreaterThanOrEqual(0); expect(b.x+b.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  await page.waitForTimeout(1000); await expect(capsule).toBeVisible(); expect(queries).toBe(1)
  release(); await expect(capsule).toHaveCount(0); await expect(page.getByRole('alert')).not.toContainText('private')
  await expect(page.getByRole('button', { name: '开始推荐' })).toBeEnabled()
})
