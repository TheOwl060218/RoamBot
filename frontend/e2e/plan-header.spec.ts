import { expect, test } from '@playwright/test'
import { workbenchPlan } from '../tests/fixtures/workbenchPlan'

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
