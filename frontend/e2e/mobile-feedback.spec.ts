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

test('mobile feedback floats without consuming form space and cancellation stays on query', async ({ page }, info) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 401, json: { error: { code: 'unauthorized', message: '请登录' } } }))
  await page.goto('/recommend')
  const distance = page.getByLabel('最大距离（km）', { exact: true })
  await distance.fill('0')
  const before = await page.locator('.travel-form').boundingBox()
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  const bubble = page.getByRole('alert', { name: '请检查填写内容' })
  await expect(bubble).toBeVisible()
  if (info.project.name.startsWith('mobile')) {
    expect((await page.locator('.travel-form').boundingBox())!.height).toBe(before!.height)
    await expect.poll(async () => (await bubble.boundingBox())!.width).toBe(page.viewportSize()!.width - 24)
    expect(await bubble.evaluate(el => getComputedStyle(el).paddingTop)).toBe('10px')
  }
  await page.screenshot({ path: `../test-results/mobile-validation-${info.project.name}.png` })
  await distance.fill('50')
  await page.getByRole('link', { name: '计划中心', exact: true }).click()
  await expect(page).toHaveURL(/\/recommend$/)
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page).toHaveURL(/\/recommend$/)
  await expect(distance).toHaveValue('50')
  await page.screenshot({ path: `../test-results/mobile-feedback-${info.project.name}.png` })
})
