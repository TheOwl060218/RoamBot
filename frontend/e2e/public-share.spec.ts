import { expect, test } from '@playwright/test'

import { registerUser, submitRecommendation } from './helpers'

test('anonymous share omits account and origin details', async ({ browser, page }, testInfo) => {
  await page.goto('/')
  const username = await registerUser(page, `share_${testInfo.project.name.replaceAll('-', '_')}`)
  await submitRecommendation(page)
  await page.goto('/history')
  await page.getByRole('button', { name: '更多历史操作', exact: true }).click()

  const shareResponsePromise = page.waitForResponse((response) => (
    response.request().method() === 'POST' && response.url().endsWith('/share')
  ))
  await page.getByRole('button', { name: '创建分享', exact: true }).click()
  const shareResponse = await shareResponsePromise
  const { share } = await shareResponse.json() as { share: { url: string } }

  await page.locator('.history-row-main').first().click()
  const backButton = await page.locator('.history-detail-actions .link-button').boundingBox()
  const shareSlot = await page.locator('.history-detail-share-slot').boundingBox()
  expect(backButton).not.toBeNull()
  expect(shareSlot).not.toBeNull()
  expect(shareSlot!.y).toBeGreaterThanOrEqual(backButton!.y + backButton!.height)

  const anonymousContext = await browser.newContext()
  const anonymousPage = await anonymousContext.newPage()
  await anonymousPage.goto(new URL(share.url, page.url()).href)
  await expect(anonymousPage.getByRole('heading', { name: '苏州出行结果', exact: true })).toBeVisible()
  await expect(anonymousPage.getByRole('heading', { name: '金鸡湖景区', exact: true })).toBeVisible()
  await expect(anonymousPage.getByText('苏州站', { exact: true })).toHaveCount(0)
  await expect(anonymousPage.getByText(username, { exact: true })).toHaveCount(0)
  const sharedResult = anonymousPage.locator('.shared-result').first()
  const sharedLayout = await sharedResult.evaluate((element) => ({
    columnCount: getComputedStyle(element).gridTemplateColumns.split(' ').length,
    pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }))
  expect(sharedLayout.columnCount).toBe(1)
  expect(sharedLayout.pageOverflow).toBeLessThanOrEqual(1)
  await anonymousContext.close()
})
