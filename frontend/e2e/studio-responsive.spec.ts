import { expect, test } from '@playwright/test'
import { studioResponse } from '../tests/fixtures/studio'
for (const width of [1440,1280,390,320]) {
  test(`studio ${width}px contains long names, seven days and composer without obstruction`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width < 600 ? 844 : 900 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const result = structuredClone(studioResponse)
    for (const item of result.items) {
      item.destination.name += '很长的景点名称'.repeat(3)
      item.weather = Array.from({ length: 7 }, (_, i) => ({ ...item.weather[0], date: `2026-10-${String(11+i).padStart(2,'0')}` }))
      item.daily_suitability = item.weather.map(day => ({ ...item.daily_suitability[0], date: day.date, summary: '' }))
    }
    await page.addInitScript(data => sessionStorage.setItem('roambot.session.search-result.v1', JSON.stringify(data)), result)
    await page.goto('/recommend')
    await expect(page.getByTestId('destination-card')).toHaveCount(3)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath(`studio-${width}-cards.png`), fullPage: true })
    for (let i = 0; i < 3; i++) await page.getByRole('button', { name: /^加入候选：/ }).first().click()
    await page.getByRole('button', { name: '查看对比（3）' }).click()
    await expect(page.locator('.comparison-card-grid article')).toHaveCount(3)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
    await page.getByRole('button', { name: '收起对比' }).click()
    await page.getByRole('button', { name: /^了解/ }).first().click()
    await expect(page.locator('.weather-day')).toHaveCount(7)
    await page.getByText('匹配指数如何计算').click()
    expect(await page.locator('.destination-detail').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
    expect(await page.locator('.destination-detail').evaluate(el => el.scrollHeight >= el.clientHeight)).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
    expect(await page.locator('.destination-detail').evaluate(el => getComputedStyle(el).animationName)).toBe('none')
    await page.screenshot({ path: info.outputPath(`studio-${width}-details.png`), fullPage: true })
  })
}
