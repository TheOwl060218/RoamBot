import { expect, test } from '@playwright/test'
import { submitRecommendation } from './helpers'

test('real POI fixture offers detail and name search without overflowing the header', async ({ page }, info) => {
  await page.route('**/api/v1/recommendations', async route => {
    const response = await route.fetch()
    const body = await response.json()
    for (const item of body.items) {
      item.destination.provider_id = 'amap:B02000ICGL'
    }
    await route.fulfill({ response, json: body })
  })
  await page.goto('/recommend')
  await submitRecommendation(page)
  const detail = page.locator('.place-detail')
  const primary = detail.getByRole('link', { name: '在高德查看', exact: true })
  const fallback = detail.getByRole('link', { name: '按名称搜索', exact: true })
  await expect(primary).toBeVisible()
  await expect(fallback).toBeVisible()
  const detailUrl = new URL((await primary.getAttribute('href'))!)
  expect(detailUrl.hostname).toBe('uri.amap.com')
  expect(detailUrl.pathname).toBe('/poidetail')
  expect(detailUrl.searchParams.get('poiid')).toBe('B02000ICGL')
  const searchUrl = new URL((await fallback.getAttribute('href'))!)
  expect(searchUrl.pathname).toBe('/search')
  expect(searchUrl.searchParams.get('keyword')).toBe(await detail.locator('h2').innerText())
  expect(searchUrl.searchParams.get('city')).toBe('苏州')
  for (const link of [primary, fallback]) {
    await expect(link).toHaveAttribute('target', '_blank')
    await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  }
  expect(await detail.locator('.result-header').evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await detail.scrollIntoViewIfNeeded()
  await page.screenshot({ path: `../evidence/amap-actions-${info.project.name}-20261009.png` })
})
