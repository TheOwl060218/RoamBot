import { expect, test } from '@playwright/test'

import { submitRecommendation } from './helpers'

test('guest receives a demo recommendation without writing history', async ({ page }) => {
  let historyRequests = 0
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/v1/history')) historyRequests += 1
  })

  await page.goto('/recommend')

  const submit = page.getByRole('button', { name: '开始推荐' })
  await expect(submit).toHaveCSS('border-radius', '999px')
  await expect(page.locator('.brand-mark')).toHaveCSS('background-color', 'rgb(23, 111, 138)')

  await submitRecommendation(page)

  await expect(page.locator('.destination-detail .detail-title-row')).toContainText('出游匹配指数')
  await expect(page.locator('.studio-disclaimer')).toHaveCount(0)
  expect(historyRequests).toBe(0)
})
