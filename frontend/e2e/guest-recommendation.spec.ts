import { expect, test } from '@playwright/test'

import { submitRecommendation } from './helpers'

test('guest receives a demo recommendation without writing history', async ({ page }) => {
  let historyRequests = 0
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/v1/history')) historyRequests += 1
  })

  await page.goto('/')
  await submitRecommendation(page)

  await expect(page.getByText('出游匹配指数', { exact: true })).toBeVisible()
  await expect(page.getByText(
    '地点评分数据来源：高德开放平台；出游匹配指数仅用于比较本次候选地点，不代表官方评价。',
    { exact: true },
  )).toBeVisible()
  expect(historyRequests).toBe(0)
})
