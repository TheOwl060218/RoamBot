import { expect, test } from '@playwright/test'
import { workbenchPlan } from '../tests/fixtures/workbenchPlan'

for (const role of ['owner', 'voter']) {
  test(`${role} final marker does not displace candidate information`, async ({ page }) => {
    const plan = workbenchPlan()
    plan.status = 'decided'
    plan.final_candidate_id = '1'
    await page.route('**/api/v1/**', route => route.fulfill({ json: new URL(route.request().url()).pathname.endsWith('/auth/me')
      ? { user: role === 'owner' ? { username: 'fixture' } : null }
      : { plan, anonymous_csrf: 'fixture' } }))
    await page.goto(role === 'owner' ? '/plans/workbench' : '/join/fixture')
    const cards = page.locator('.plan-comparison-card')
    await expect(cards).toHaveCount(3)
    const selected = cards.first()
    await expect(selected.getByText('最终目的地', { exact: true })).toBeVisible()
    for (const selector of ['.plan-candidate-address', '.plan-metrics', '.plan-selected-weather', '.plan-candidate-actions']) {
      const boxes = await cards.locator(selector).evaluateAll(elements => elements.map(el => el.getBoundingClientRect().top))
      expect(Math.max(...boxes) - Math.min(...boxes)).toBeLessThanOrEqual(1)
    }
    plan.candidates[1].snapshot.destination.name = '这是一个名称非常长的最终目的地用于检查移动端和桌面端卡片对齐'
    await page.reload()
    await expect(selected.getByRole('heading', { name: plan.candidates[1].snapshot.destination.name })).toBeVisible()
    await expect(selected.getByText('最终目的地', { exact: true })).toBeVisible()
    const positions = await cards.locator('.plan-metrics').evaluateAll(elements => elements.map(el => el.getBoundingClientRect().top))
    expect(Math.max(...positions) - Math.min(...positions)).toBeLessThanOrEqual(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
