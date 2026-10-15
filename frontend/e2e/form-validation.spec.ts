import { expect, test } from '@playwright/test'
import { fillStudioConditions, registerUser } from './helpers'
test('validation announces visible errors without queries and native bubbles', async ({ page }) => {
  await page.goto('/recommend'); let queries = 0
  page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/recommendations')) queries++ })
  await page.getByRole('button', { name: '开始推荐' }).click()
  await expect(page.getByRole('alert')).toContainText('主出发地')
  await fillStudioConditions(page)
  await page.getByRole('button', { name: /编辑目的地范围/ }).click()
  await page.getByLabel('最大距离（km）').fill('500000')
  await page.getByRole('button', { name: '保存条件' }).click()
  await page.getByRole('button', { name: '开始推荐' }).click()
  const bubble = page.getByRole('alert'); await expect(bubble).toContainText('距离')
  const b = (await bubble.boundingBox())!; expect(b.x).toBeGreaterThanOrEqual(0); expect(b.x + b.width).toBeLessThanOrEqual(page.viewportSize()!.width); expect(b.y + b.height).toBeLessThan(page.viewportSize()!.height)
  expect(queries).toBe(0)
  expect(await bubble.evaluate(el => getComputedStyle(el).position)).toBe('fixed')
  await registerUser(page, 'validation'); await page.goto('/plans')
  const start = page.getByRole('link', { name: '开始一次推荐' }); await expect(start).toBeVisible()
  expect(await start.evaluate(el => getComputedStyle(el).textDecorationLine)).toBe('none')
})
