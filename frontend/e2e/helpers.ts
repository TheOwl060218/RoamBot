import { expect, type Page } from '@playwright/test'

export function tomorrowInChina() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(Date.now() + 86_400_000))
}

export async function submitRecommendation(page: Page) {
  const date = tomorrowInChina()
  await page.getByLabel('主出发地', { exact: true }).fill('苏州站')
  await page.getByLabel('最大距离（km）', { exact: true }).fill('80')
  await page.getByLabel('开始日期', { exact: true }).fill(date)
  await page.getByLabel('结束日期', { exact: true }).fill(date)
  await page.getByRole('checkbox', { name: '湖景', exact: true }).check()
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  await expect(page.locator('.place-detail')).toBeVisible()
  await expect(page.getByRole('button', { name: '修改条件', exact: true })).toBeVisible()
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
