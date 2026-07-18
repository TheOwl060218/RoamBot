import { expect, test } from '@playwright/test'

import { submitRecommendation } from './helpers'

test('guest receives a demo recommendation without writing history', async ({ page }) => {
  let historyRequests = 0
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/v1/history')) historyRequests += 1
  })

  await page.goto('/')
  await submitRecommendation(page)

  await expect(page.getByText('推荐指数', { exact: true })).toBeVisible()
  expect(historyRequests).toBe(0)
})
