import { expect, test } from '@playwright/test'
import { workbenchPlan } from '../tests/fixtures/workbenchPlan'

for (const role of ['owner', 'voter']) {
  test(`${role} explanation preserves layout and stays within screen edges`, async ({ page }, info) => {
    const plan = workbenchPlan()
    plan.candidates[2].snapshot.daily_suitability![0].summary = '户外出行请留意降雨，准备雨具并及时调整路线。'.repeat(30)
    await page.route('**/api/v1/**', route => route.fulfill({ json: new URL(route.request().url()).pathname.endsWith('/auth/me')
      ? { user: role === 'owner' ? { username: 'fixture' } : null }
      : { plan, anonymous_csrf: 'fixture' } }))
    await page.goto(role === 'owner' ? '/plans/workbench' : '/join/fixture')
    await page.getByRole('button', { name: '查看全部日期', exact: true }).click()
    const trigger = page.getByRole('button', { name: '查看苏州博物馆详情' })
    await trigger.scrollIntoViewIfNeeded()
    const before = (await trigger.boundingBox())!
    const card = page.locator('.plan-comparison-card').first()
    const height = (await card.boundingBox())!.height
    const table = page.getByRole('table', { name: '全部日期天气对比' })
    const tableY = (await table.boundingBox())!.y
    await trigger.click()
    const popup = page.getByRole('dialog', { name: '苏州博物馆 · 12.30 出行说明' })
    await expect(popup).toBeVisible()
    const after = (await page.getByRole('button', { name: '收起苏州博物馆详情' }).boundingBox())!
    expect(Math.abs(after.x - before.x)).toBeLessThan(1)
    expect(Math.abs(after.y - before.y)).toBeLessThan(1)
    expect(Math.abs((await card.boundingBox())!.height - height)).toBeLessThan(1)
    expect(Math.abs((await table.boundingBox())!.y - tableY)).toBeLessThan(1)
    const bounds = (await popup.boundingBox())!, viewport = page.viewportSize()!
    const visibleWidth = await page.evaluate(() => document.documentElement.clientWidth)
    expect(bounds.x).toBeGreaterThanOrEqual(12)
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(visibleWidth - 12)
    expect(bounds.y).toBeGreaterThanOrEqual((await page.locator('.shell-header').boundingBox())!.height)
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(viewport.height - 12)
    expect(bounds.y + bounds.height <= before.y || bounds.y >= before.y + before.height).toBe(true)
    await page.screenshot({ path: info.outputPath(`${role}-day-explanation.png`) })
    await page.mouse.click(before.x + before.width / 2, before.y + before.height / 2)
    await expect(popup).toHaveCount(0)
    await trigger.click()
    await page.keyboard.press('Escape')
    await expect(popup).toHaveCount(0)
    await expect(trigger).toBeFocused()
    await trigger.click()
    await page.getByRole('button', { name: '12.31', exact: true }).click()
    await expect(popup).toHaveCount(0)
    await page.getByRole('button', { name: '12.30', exact: true }).click()
    await expect(trigger).toHaveAttribute('aria-expanded', 'false')
    // Added after GREEN: long content at the right edge must scroll inside the popup.
    const rightTrigger = page.getByRole('button', { name: '查看穹窿山详情' })
    await rightTrigger.scrollIntoViewIfNeeded()
    await rightTrigger.click()
    const rightPopup = page.getByRole('dialog', { name: '穹窿山 · 12.30 出行说明' })
    await expect(rightPopup).toBeVisible()
    const rightBounds = (await rightPopup.boundingBox())!
    expect(rightBounds.x + rightBounds.width).toBeLessThanOrEqual(visibleWidth - 12)
    expect(rightBounds.y + rightBounds.height).toBeLessThanOrEqual(viewport.height - 12)
    expect(await rightPopup.evaluate(el => el.scrollHeight > el.clientHeight)).toBe(true)
    await page.keyboard.press('Escape')
    if (info.project.name === 'desktop-chromium') {
      await page.getByRole('button', { name: '去投票', exact: true }).click()
      await rightTrigger.click()
      await page.keyboard.press('Escape')
      await expect(rightPopup).toHaveCount(0)
      await expect(page.getByRole('dialog', { name: '我的投票', exact: true })).toBeVisible()
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
