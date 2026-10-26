import { expect, test } from '@playwright/test'
import { fillStudioConditions } from './helpers'

test('outgoing pages retain their content bounds in both directions', async ({ page }) => {
  await page.goto('/recommend')
  await fillStudioConditions(page)
  const query = await page.locator('.studio-query-page').boundingBox()
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'toResults')
  const leavingQuery = await page.locator('.studio-query-page').boundingBox()
  expect(Math.abs(leavingQuery!.width - query!.width)).toBeLessThan(1)
  expect(Math.abs(leavingQuery!.x - query!.x)).toBeLessThan(1)
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  const results = await page.locator('.studio-results-page').boundingBox()
  await page.getByRole('button', { name: '← 返回修改' }).click()
  const leavingResults = await page.locator('.studio-results-page').boundingBox()
  expect(Math.abs(leavingResults!.width - results!.width)).toBeLessThan(1)
  expect(Math.abs(leavingResults!.x - results!.x)).toBeLessThan(1)
})

test('closing layers retain their full visual content until the exit finishes', async ({ page }) => {
  await page.route('**/api/v1/maps/config', route => route.fulfill({ json: { enabled: false } }))
  await page.goto('/recommend')
  await fillStudioConditions(page)
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await page.getByRole('button', { name: /^了解/ }).first().click()
  const endpoint = await page.locator('.coastal-motion-ghost').evaluate(ghost => {
    const element = ghost as HTMLElement
    const keyframe = element.getAnimations()[0].effect!.getKeyframes().at(-1)!
    const matrix = new DOMMatrix(String(keyframe.transform))
    return { x: parseFloat(element.style.left) + matrix.m41, y: parseFloat(element.style.top) + matrix.m42,
      width: parseFloat(element.style.width) * matrix.m11, height: parseFloat(element.style.height) * matrix.m22 }
  })
  await page.waitForTimeout(520)
  const settled = await page.locator('.destination-detail').boundingBox()
  for (const key of ['x', 'y', 'width', 'height'] as const) expect(Math.abs(endpoint[key] - settled![key])).toBeLessThan(1)
  await page.getByRole('button', { name: '查看位置', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '景点位置' })).toBeVisible()
  await page.waitForTimeout(350)
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-exit-snapshot] .location-dialog')).toHaveCount(1)
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
  await expect(page.locator('.destination-detail')).toBeVisible()
  await page.goBack()
  await expect(page.locator('[data-exit-snapshot] .destination-detail')).toHaveCount(1)
  await expect(page.locator('[data-exit-snapshot] .detail-overview')).toHaveCount(1)
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^了解/ }).first()).toBeFocused()
})

test('guest plan navigation enters its page instead of opening an unrelated modal', async ({ page }) => {
  await page.goto('/recommend')
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '计划中心', exact: true }).click()
  await expect(page).toHaveURL(/\/plans$/)
  await expect(page.getByText('登录后可查看此页面。')).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('account exit is visual-only, excludes password values, and respects reduced motion', async ({ page }) => {
  await page.goto('/recommend')
  await page.getByRole('button', { name: '账户', exact: true }).click()
  await page.getByLabel('密码', { exact: true }).fill('temporary-private-input')
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  const snapshot = page.locator('[data-exit-snapshot]')
  await expect(snapshot.locator('.auth-dialog')).toHaveCount(1)
  await expect(snapshot.locator('input[type=password]')).toHaveValue('')
  await expect(snapshot).toHaveCount(0)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('button', { name: '账户', exact: true }).click()
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(snapshot).toHaveCount(0)
  await expect(page.getByRole('button', { name: '账户', exact: true })).toBeFocused()
})
