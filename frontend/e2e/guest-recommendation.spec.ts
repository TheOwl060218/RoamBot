import { expect, test } from '@playwright/test'

import { submitRecommendation } from './helpers'

test('guest receives a demo recommendation without writing history', async ({ page }) => {
  let historyRequests = 0
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/v1/history')) historyRequests += 1
  })

  await page.goto('/')

  const submit = page.getByRole('button', { name: '开始推荐' })
  await expect(submit).toHaveCSS('border-radius', '999px')
  await expect(page.locator('.brand-mark')).toHaveCSS('background-color', 'rgb(23, 111, 138)')

  await submitRecommendation(page)

  await expect(page.getByText('出游匹配指数', { exact: true })).toBeVisible()
  await expect(page.getByText(
    '天气数据来自和风天气；地点评分来自高德开放平台；距离与用时按查询时驾车路况估算；出游匹配指数仅用于比较本次候选地点。',
    { exact: true },
  )).toBeVisible()
  expect(historyRequests).toBe(0)
})
