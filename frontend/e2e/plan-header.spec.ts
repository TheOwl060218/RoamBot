import { expect, test } from '@playwright/test'
import { workbenchPlan } from '../tests/fixtures/workbenchPlan'

test('mobile active plan stays one line and truncates its expanded destination', async ({ page }, info) => {
  test.skip(!info.project.name.startsWith('mobile'), 'mobile-only capsule')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const plan = workbenchPlan()
  plan.status = 'decided'
  plan.final_candidate_id = '0'
  plan.candidates[0].snapshot.destination.name = '金鸡湖景区特别长的地点名称用于检查单行省略显示'
  await page.route('**/api/v1/**', route => route.fulfill({ json: new URL(route.request().url()).pathname.endsWith('/auth/me')
    ? { user: { username: 'fixture' } } : { plans: [plan] } }))
  await page.goto('/recommend')
  const capsule = page.locator('.mobile-plan-anchor .plan-status-link')
  await expect(capsule).toHaveClass(/expanded/)
  expect((await capsule.boundingBox())!.height).toBe(36)
  const detail = capsule.locator('.plan-status-detail')
  await expect(detail).toBeVisible()
  expect(await detail.evaluate(el => el.scrollWidth > el.clientWidth && getComputedStyle(el).textOverflow === 'ellipsis')).toBe(true)
  const titleBox = (await capsule.locator('.plan-status-title').boundingBox())!
  const detailBox = (await detail.boundingBox())!
  expect(detailBox.x).toBeGreaterThan(titleBox.x)
  expect(Math.abs(detailBox.y + detailBox.height / 2 - titleBox.y - titleBox.height / 2)).toBeLessThan(1)
  await page.screenshot({ path: '../test-results/mobile-plan-single-line.png' })
  await expect(capsule).not.toHaveClass(/expanded/, { timeout: 6000 })
  expect((await capsule.boundingBox())!.height).toBe(36)
  await capsule.click()
  await expect(page).toHaveURL(/\/plans\/workbench$/)
})

for (const role of ['owner', 'voter']) {
  test(`${role} compact header balances title with progress and keeps weather in view`, async ({ page }, info) => {
    const plan = workbenchPlan()
    plan.participants = [{ id: 'owner', nickname: '发起者', role: 'owner', voted: true }, { id: 'a', nickname: '同行甲', role: 'guest', voted: true }, { id: 'b', nickname: '同行乙', role: 'guest', voted: false }]
    if (role === 'voter') plan.participants = null
    await page.route('**/api/v1/**', route => route.fulfill({ json: new URL(route.request().url()).pathname.endsWith('/auth/me')
      ? { user: role === 'owner' ? { username: 'fixture' } : null }
      : { plan, anonymous_csrf: 'fixture' } }))
    await page.goto(role === 'owner' ? '/plans/workbench' : '/join/fixture')
    const heading = page.getByRole('heading', { name: plan.name, exact: true })
    await expect(heading).toBeVisible()
    const progress = page.getByRole('region', { name: '同行进展' })
    await expect(progress).toBeVisible()
    if (role === 'owner') await expect(progress.getByText('2/3 人已投票')).toBeVisible()
    else await expect(progress.getByText('先投票，再查看进展')).toBeVisible()
    const titleBox = (await heading.boundingBox())!, progressBox = (await progress.boundingBox())!
    if (info.project.name.startsWith('desktop')) {
      expect(progressBox.x).toBeGreaterThan(titleBox.x + titleBox.width)
      expect(Number(await heading.evaluate(el => parseFloat(getComputedStyle(el).fontSize)))).toBeLessThanOrEqual(26)
      const weather = (await page.locator('.plan-selected-weather').first().boundingBox())!
      expect(weather.y + weather.height).toBeLessThan(page.viewportSize()!.height)
    } else expect(progressBox.y).toBeGreaterThan(titleBox.y + titleBox.height)
    await page.screenshot({ path: info.outputPath(`${role}-compact-header.png`) })
    plan.name = '这是一个较长的同行出行计划名称用于验证标题换行后仍然保持布局完整'
    await page.reload()
    await expect(page.getByRole('heading', { name: plan.name })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
