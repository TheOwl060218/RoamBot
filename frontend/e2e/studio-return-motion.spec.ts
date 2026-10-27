import { test, expect } from '@playwright/test'
import { fillStudioConditions } from './helpers'

test('returning conditions unfold inside the incoming page without a second landing jump', async ({ page }, testInfo) => {
  await page.goto('/recommend')
  await fillStudioConditions(page)
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
  await page.getByRole('button', { name: '← 返回修改' }).click()
  const middle = await page.evaluate(() => {
    for (const animation of document.getAnimations()) {
      animation.pause()
      animation.currentTime = 580
    }
    const puzzle = document.querySelector('.studio-query-page .condition-puzzle')!
    return { opacity: Number(getComputedStyle(puzzle).opacity), floatingCopies: document.querySelectorAll('body > .puzzle-travel-ghost').length }
  })
  await page.screenshot({ path: testInfo.outputPath('return-mid.png') })
  expect(middle.opacity).toBeGreaterThan(.9)
  expect(middle.floatingCopies).toBe(0)
  await page.evaluate(() => { for (const animation of document.getAnimations()) animation.finish() })
  await expect(page.locator('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'query')
  const landing = await page.locator('.studio-query-page .condition-piece').evaluateAll(nodes =>
    nodes.map(node => ({ animations: node.getAnimations().filter(animation => animation.playState === 'running').length,
      transform: getComputedStyle(node).transform })))
  expect(landing.every(piece => piece.animations === 0 && piece.transform === 'none')).toBe(true)
  await expect(page.getByRole('button', { name: /编辑出发地/ })).toContainText('苏州站')
})
