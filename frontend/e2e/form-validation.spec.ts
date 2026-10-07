import { expect, test } from '@playwright/test'
import { registerUser } from './helpers'

test('invalid recommendation announces errors above the form on desktop and mobile', async ({ page }) => {
  await page.goto('/')
  let recommendationRequests = 0
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/recommendations')) recommendationRequests++
  })
  await page.getByLabel('最大距离（km）', { exact: true }).fill('500000')
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  const bubble = page.getByRole('alert', { name: '请检查填写内容' })
  await expect(bubble).toBeVisible()
  await expect(bubble).toContainText('最大距离')
  await expect(bubble).toContainText('主出发地')
  const geometry = await bubble.evaluate(element => {
    const box = element.getBoundingClientRect()
    const header = document.querySelector('.shell-header')!.getBoundingClientRect()
    return { left: box.left, right: box.right, top: box.top, bottom: box.bottom,
      headerBottom: header.bottom, width: document.documentElement.clientWidth, height: window.innerHeight,
      position: getComputedStyle(element).position }
  })
  expect(geometry.position).toBe('fixed')
  expect(geometry.left).toBeGreaterThanOrEqual(0)
  expect(geometry.right).toBeLessThanOrEqual(geometry.width)
  expect(geometry.top).toBeGreaterThan(geometry.headerBottom)
  expect(geometry.bottom).toBeLessThan(geometry.height)
  expect(recommendationRequests).toBe(0)
  await expect(bubble).toBeHidden({ timeout: 3500 })
  await registerUser(page, 'bubble')
  await page.goto('/plans')
  const start = page.getByRole('link', { name: '开始一次推荐' })
  await expect(start).toBeVisible()
  const style = await start.evaluate(element => ({
    decoration: getComputedStyle(element).textDecorationLine,
    color: getComputedStyle(element).color,
  }))
  expect(style.decoration).toBe('none')
  expect(style.color).toBe('rgb(23, 111, 138)')
})
