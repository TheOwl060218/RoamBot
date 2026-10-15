import { expect, test } from '@playwright/test'
import { tomorrowInChina } from './helpers'

test('long names stay inside a bounded independent pocket at ultrawide and narrow widths', async ({ page }, info) => {
  const day = tomorrowInChina()
  await page.addInitScript(({ day }) => sessionStorage.setItem('roambot.studio.session.v1', JSON.stringify({
    version: 2, confirmedFields: ['range'], draft: {
      mode: 'recommendation', city: '苏州', mainOrigin: '南京大学苏州校区东区主要出发地点名称较长',
      companions: ['乌鲁木齐南站出发地点名称较长', '上海虹桥站'],
      mainOriginCoordinate: null, companionOriginCoordinates: [null, null],
      startDate: day, endDate: day, maxDistance: '50', sceneryTypes: ['lake'],
      sceneryQuery: '想去安静的湖边散步，附近可以拍照，不想去太远的地方', matchMode: 'any', targetPlace: '',
      destinationRegions: ['650100', '310000', '320500'], weights: { weather: 40, distance: 30, popularity: 30 },
    },
  })), { day })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 1920, height: 1080 })
  await page.goto('/recommend')
  await expect(page.locator('.studio-query-page .condition-piece')).toHaveCount(6)
  const workspace = page.locator('.spatial-workspace')
  expect((await workspace.boundingBox())!.width).toBeLessThan(1700)
  await page.screenshot({ path: info.outputPath('ultrawide-long-names.png') })
  await page.setViewportSize({ width: 320, height: 844 })
  const pocket = page.locator('.condition-pocket-scroll')
  const metrics = await pocket.evaluate(el => ({ height: el.clientHeight, content: el.scrollHeight }))
  expect(metrics.content).toBeGreaterThan(metrics.height)
  expect(metrics.height).toBeLessThanOrEqual(240)
  const outerY = await page.evaluate(() => scrollY)
  await pocket.evaluate(el => { el.scrollTop = el.scrollHeight })
  expect(await page.evaluate(() => scrollY)).toBe(outerY)
  await page.screenshot({ path: info.outputPath('narrow-pocket.png') })
  await page.getByRole('button', { name: /编辑推荐偏好/ }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('dialog', { name: '偏好权重', exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: /编辑推荐偏好/ })).toBeFocused()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
