import { expect, type Page } from '@playwright/test'

export function tomorrowInChina() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(Date.now() + 86_400_000))
}

export async function fillStudioConditions(page: Page, scenery = ['湖景']) {
  if (await page.getByRole('button', { name: '← 返回修改' }).isVisible()) {
    await page.getByRole('button', { name: '← 返回修改' }).click()
  }
  await page.getByRole('textbox', { name: '继续补充条件' }).fill(`明天从苏州站出发，80公里内，想去${scenery.join('和')}`)
  await page.getByRole('button', { name: '发送消息' }).click()
  await expect(page.getByRole('button', { name: /编辑出发地/ })).toContainText('苏州站')
  await expect(page.getByRole('button', { name: '开始推荐', exact: true })).toBeEnabled()
}
export async function submitRecommendation(page: Page) {
  await fillStudioConditions(page)
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  await expect(page.getByTestId('destination-card').first()).toBeVisible()
  await page.getByRole('button', { name: /^了解/ }).first().click()
  await expect(page.locator('.destination-detail')).toBeVisible()
  await expect(page.getByRole('button', { name: '← 返回修改' })).toBeVisible()
  await expect(page.getByText('演示数据', { exact: true })).toBeVisible()
}

export async function registerUser(page: Page, suffix: string) {
  if (await page.getByRole('dialog').count() === 0) {
    await page.getByRole('button', { name: '账户', exact: true }).click()
  }
  await page.getByRole('tab', { name: '创建账户', exact: true }).click()
  const unique = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`
  const username = `qa_${suffix.slice(0, 5)}_${unique}`
  await page.getByLabel('用户名', { exact: true }).fill(username)
  await page.getByLabel('密码', { exact: true }).fill('RoamBotDemo123!')
  await page.getByRole('button', { name: '注册并登录', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  return username
}
