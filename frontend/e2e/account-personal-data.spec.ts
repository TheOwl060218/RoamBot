import { expect, test } from '@playwright/test'

import { registerUser, submitRecommendation } from './helpers'

test('account keeps favorites and history through the main workflow', async ({ page }, testInfo) => {
  await page.goto('/favorites')
  await expect(page.getByRole('dialog', { name: '登录 RoamBot', exact: true })).toBeVisible()
  await registerUser(page, testInfo.project.name.replaceAll('-', '_'))
  await expect(page.getByRole('heading', { name: '收藏', exact: true })).toBeVisible()

  await page.goto('/')
  await submitRecommendation(page)
  await page.getByRole('button', { name: '收藏地点', exact: true }).click()

  await page.goto('/favorites')
  await expect(page.getByRole('heading', { name: '金鸡湖景区', exact: true })).toBeVisible()

  await page.goto('/history')
  await expect(page.getByRole('heading', { name: '地点推荐 · 苏州', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '更多历史操作', exact: true }).click()

  const shareResponsePromise = page.waitForResponse((response) => (
    response.request().method() === 'POST' && response.url().endsWith('/share')
  ))
  await page.getByRole('button', { name: '创建分享', exact: true }).click()
  const shareResponse = await shareResponsePromise
  const { share } = await shareResponse.json() as {
    share: { history_id: string; url: string }
  }

  await page.getByRole('button', { name: '更多历史操作', exact: true }).click()
  await page.getByRole('button', { name: '重新查询', exact: true }).click()
  await expect(page).toHaveURL(/\/history\/[^/]+$/)
  await expect(page.getByRole('heading', { name: '历史快照', exact: true })).toBeVisible()

  await page.goto('/history')
  const sourceHistory = page.locator(`[data-history-id="${share.history_id}"]`)
  await expect(sourceHistory).toHaveCount(1)
  await sourceHistory.getByRole('button', { name: '更多历史操作', exact: true }).click()
  await page.getByRole('button', { name: '删除历史', exact: true }).click()
  const confirmDialog = page.getByRole('alertdialog', { name: '删除这条历史？', exact: true })
  await expect(confirmDialog).toBeVisible()
  await confirmDialog.getByRole('button', { name: '删除历史', exact: true }).click()
  await expect(sourceHistory).toHaveCount(0)

  await page.goto(new URL(share.url, page.url()).href)
  await expect(page.getByText('分享链接不可用或已撤销', { exact: true })).toBeVisible()

  await page.goto('/favorites')
  await expect(page.getByRole('heading', { name: '金鸡湖景区', exact: true })).toBeVisible()
  await page.getByRole('link', { name: '重新评估', exact: true }).click()
  await expect(page.getByRole('radio', { name: '评估指定地点', exact: true })).toBeChecked()
  await expect(page.getByLabel('目标地点', { exact: true })).toHaveValue('金鸡湖景区')
})
