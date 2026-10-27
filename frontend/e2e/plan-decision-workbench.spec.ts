import { fulfillApiFixture } from './helpers'
import { expect, test, type Locator, type Page } from '@playwright/test'
import { workbenchPlan } from '../tests/fixtures/workbenchPlan'

async function alignedBounds(page: Page, locators: Locator[]) {
  // The route wrapper can still translate while its children have no animation.
  // Read related controls atomically, rather than comparing different frames.
  await page.evaluate(async () => {
    await Promise.allSettled(document.getAnimations().filter(animation => animation.effect?.getComputedTiming().iterations !== Infinity).map(animation => animation.finished))
  })
  const nodes = await Promise.all(locators.map(locator => locator.elementHandle()))
  try { return await page.evaluate(elements => elements.map(node => node!.getBoundingClientRect().toJSON()), nodes) }
  finally { await Promise.all(nodes.map(node => node?.dispose())) }
}


test('one and two candidates do not add empty cards and reduced motion preserves the draft', async ({ page }, info) => {
  const plan = workbenchPlan()
  plan.candidates = plan.candidates.slice(0, 1)
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    return fulfillApiFixture(route, { json: path.endsWith('/auth/me') ? { user: null } : { plan, anonymous_csrf: 'fixture' } })
  })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/join/fixture')
  const cards = page.locator('.plan-comparison-card')
  await expect(cards).toHaveCount(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  plan.candidates = workbenchPlan().candidates.slice(0, 2)
  await page.reload()
  await expect(cards).toHaveCount(2)
  await page.getByRole('button', { name: '去投票', exact: true }).click()
  const panel = page.getByRole('dialog', { name: '我的投票' })
  await expect(panel).toBeVisible()
  expect(await page.locator('.plan-decision-workspace').evaluate(node => getComputedStyle(node).transitionDuration)).toBe('0s')
  await page.getByRole('radio', { name: '首选 金鸡湖' }).check()
  await page.keyboard.press('Escape')
  await expect(panel).toBeHidden()
  await expect(page.getByRole('button', { name: '继续投票', exact: true })).toBeFocused()
  await page.getByRole('button', { name: '继续投票', exact: true }).click()
  await expect(page.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('two-candidate-reduced-motion.png') })
})

for (const role of ['owner', 'voter']) {
  test(`${role} workbench compares three candidates without covering desktop content`, async ({ page }, info) => {
    let plan = workbenchPlan()
    plan.start_date = '2026-12-01'; plan.end_date = '2026-12-06'
    for (const candidate of plan.candidates) {
      candidate.snapshot.weather = Array.from({ length: 6 }, (_, i) => ({ ...candidate.snapshot.weather[0], date: `2026-12-0${i + 1}`, condition: i % 2 ? '小雨' : '多云' }))
      candidate.snapshot.daily_suitability = candidate.snapshot.weather.map(day => ({ date: day.date, score: 85, status: 'suitable', summary: '携带雨具，留意路面情况。', reasons: [] }))
    }
    let votes = 0
    await page.route('**/api/v1/**', async route => {
      const path = new URL(route.request().url()).pathname
      if (path.endsWith('/vote')) {
        votes++
        expect(route.request().method()).toBe('PUT')
        expect(route.request().postDataJSON()).toEqual({ preferred_id: '1', acceptable_ids: [] })
        if (role === 'voter') expect(route.request().headers()['x-plan-csrf']).toBe('fixture')
        plan = { ...plan, me: { ...plan.me!, preferred_id: '1' } }
      }
      await fulfillApiFixture(route, { json: path.endsWith('/auth/me') ? role === 'owner' ? { user: { username: 'fixture' }, csrf_token: 'fixture' } : { user: null } : path.endsWith('/plans') ? { plans: [] } : { plan, anonymous_csrf: 'fixture' } })
    })
    await page.goto(role === 'owner' ? '/plans/workbench' : '/join/fixture')
    const cards = page.locator('.plan-comparison-card'), comparison = page.locator('.plan-comparison-region')
    await expect(cards).toHaveCount(3)
    await expect(page.locator('.plan-date-tabs button')).toHaveCount(6)
    await expect(page.getByText('禁止展示的 AI 推荐理由')).toHaveCount(0)
    if (role === 'owner') {
      const [allDates, check, manage, heading] = await alignedBounds(page, [
        page.getByRole('button', { name: '查看全部日期', exact: true }),
        page.getByRole('button', { name: '检查天气', exact: true }),
        page.getByRole('button', { name: '管理计划', exact: true }),
        page.getByRole('heading', { name: '比较候选地点', exact: true }),
      ])
      expect(Math.abs(allDates.y - check.y)).toBeLessThan(2)
      expect(Math.abs(allDates.height - check.height)).toBeLessThan(2)
      expect(check.x - (allDates.x + allDates.width)).toBeGreaterThanOrEqual(8)
      expect(check.x - (allDates.x + allDates.width)).toBeLessThanOrEqual(14)
      expect(allDates.y).toBeGreaterThan(manage.y + manage.height)
      if (info.project.name.startsWith('desktop')) {
        expect(Math.abs(manage.y + manage.height / 2 - (heading.y + heading.height / 2))).toBeLessThan(2)
      }
    }
    await page.screenshot({ path: info.outputPath(`${role}-toolbar-closed.png`) })
    await page.getByRole('button', { name: '12.2', exact: true }).click()
    for (const card of await cards.all()) await expect(card.getByText('小雨', { exact: true })).toBeVisible()
    const original = await comparison.elementHandle()
    const widths = await page.evaluate(async () => {
      const node = document.querySelector('.plan-comparison-region')!
      const result = [node.getBoundingClientRect().width]
      const button = Array.from(document.querySelectorAll<HTMLButtonElement>('.plan-workbench-actions button')).find(b => b.textContent?.includes('去投票'))!
      button.click()
      await new Promise(resolve => setTimeout(resolve, 70))
      result.push(node.getBoundingClientRect().width)
      await new Promise(resolve => setTimeout(resolve, 280))
      result.push(node.getBoundingClientRect().width)
      return result
    })
    expect(await page.evaluate(node => node === document.querySelector('.plan-comparison-region'), original)).toBe(true)
    const desktop = info.project.name.startsWith('desktop')
    if (desktop) {
      expect(widths[0]).toBeGreaterThan(widths[1])
      expect(widths[1]).toBeGreaterThan(widths[2])
    } else expect(Math.abs(widths[0] - widths[2])).toBeLessThan(1)
    const panel = page.getByRole('dialog', { name: '我的投票' })
    await expect(panel).toBeVisible()
    await page.getByRole('radio', { name: '首选 金鸡湖' }).check()
    await page.getByRole('button', { name: '收起投票面板' }).click()
    await expect(panel).toBeHidden()
    await page.getByRole('button', { name: '继续投票', exact: true }).click()
    await expect(page.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
    await expect(page.getByRole('button', { name: '12.2', exact: true })).toHaveAttribute('aria-pressed', 'true')
    if (role === 'owner') {
      // Mobile voting is a bottom sheet: close it before using page management.
      if (!desktop) await page.getByRole('button', { name: '收起投票面板' }).click()
      await page.getByRole('button', { name: '管理计划', exact: true }).click()
      await page.getByRole('button', { name: '编辑计划信息' }).click()
      const [save, invite] = await alignedBounds(page, [page.getByRole('button', { name: '保存信息', exact: true }),
        page.getByRole('button', { name: '生成邀请', exact: true })])
      if (desktop) expect(Math.abs(save.y - invite.y)).toBeLessThan(2)
      await page.getByRole('button', { name: '收起管理', exact: true }).click()
      await page.getByRole('button', { name: '继续投票', exact: true }).click()
    } else {
      await expect(page.getByRole('button', { name: '管理计划' })).toHaveCount(0)
      await expect(page.getByRole('heading', { name: '当前投票结果' })).toHaveCount(0)
    }
    for (const width of desktop ? [1440, 1280, 1024] : [390]) {
      await page.setViewportSize({ width, height: desktop ? 900 : 650 })
      await page.waitForTimeout(350)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      for (const card of await cards.all()) expect((await card.boundingBox())!.width).toBeGreaterThanOrEqual(259)
      const left = (await comparison.boundingBox())!, right = (await panel.boundingBox())!
      if (desktop) expect(left.x + left.width).toBeLessThanOrEqual(right.x)
      else { expect(right.y).toBeGreaterThan(0); expect(right.y + right.height).toBeLessThanOrEqual(650) }
    }
    await page.screenshot({ path: info.outputPath(`${role}-workbench.png`) })
    await page.setViewportSize({ width: desktop ? 390 : 1440, height: 844 })
    await expect(page.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
    await expect(page.getByRole('dialog', { name: '我的投票' })).toHaveCount(1)
    expect(votes).toBe(0)
    await page.getByRole('button', { name: '提交投票', exact: true }).click()
    await expect(panel).toBeHidden()
    expect(votes).toBe(1)
    plan = { ...plan, status: 'closed' }
    await page.reload()
    await expect(page.getByRole('button', { name: '去投票', exact: true })).toHaveCount(0)
    await expect(page.getByRole('radio')).toHaveCount(0)
  })
}
