import { expect, test } from '@playwright/test'

test('mobile home group is centered without changing desktop alignment', async ({ page }, info) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 401, json: { error: { code: 'unauthorized', message: '请登录' } } }))
  await page.goto('/')
  await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible()
  const brand = await page.locator('.home-brand').boundingBox()
  const actions = await page.locator('.home-actions').boundingBox()
  if (info.project.name.startsWith('mobile')) {
    expect(Math.abs(actions!.x + actions!.width / 2 - page.viewportSize()!.width / 2)).toBeLessThan(1)
    expect(Math.abs(brand!.x + brand!.width / 2 - actions!.x - actions!.width / 2)).toBeLessThan(1)
  } else expect(actions!.x).toBeLessThan(page.viewportSize()!.width / 3)
  await page.screenshot({ path: `../test-results/home-centered-${info.project.name}.png` })
})

test('mobile feedback floats without changing puzzle geometry, auth cancel stays on query', async ({ page }) => {
  await page.goto('/recommend')
  const puzzle = page.getByRole('region', { name: '当前出行条件' })
  const before = (await puzzle.boundingBox())!
  await page.getByRole('button', { name: '开始推荐' }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  expect((await puzzle.boundingBox())!.height).toBe(before.height)
  await page.getByRole('link', { name: '计划中心', exact: true }).click()
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page).toHaveURL(/\/recommend$/)
  await expect(puzzle).toBeVisible()
  await expect(page.getByRole('textbox', { name: '继续补充条件' })).toBeVisible()
})
