import { expect, test } from '@playwright/test'

import { registerUser, submitRecommendation } from './helpers'

test('anonymous share omits account and origin details', async ({ browser, page }, testInfo) => {
  await page.goto('/')
  const username = await registerUser(page, `share_${testInfo.project.name.replaceAll('-', '_')}`)
  await submitRecommendation(page)
  await page.goto('/history')

  const shareResponsePromise = page.waitForResponse((response) => (
    response.request().method() === 'POST' && response.url().endsWith('/share')
  ))
  await page.getByRole('button', { name: '创建分享', exact: true }).click()
  const shareResponse = await shareResponsePromise
  const { share } = await shareResponse.json() as { share: { url: string } }

  const anonymousContext = await browser.newContext()
  const anonymousPage = await anonymousContext.newPage()
  await anonymousPage.goto(new URL(share.url, page.url()).href)
  await expect(anonymousPage.getByRole('heading', { name: '苏州出行结果', exact: true })).toBeVisible()
  await expect(anonymousPage.getByRole('heading', { name: '金鸡湖景区', exact: true })).toBeVisible()
  await expect(anonymousPage.getByText('苏州站', { exact: true })).toHaveCount(0)
  await expect(anonymousPage.getByText(username, { exact: true })).toHaveCount(0)
  await anonymousContext.close()
})
