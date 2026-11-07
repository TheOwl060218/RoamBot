import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

const preserved = JSON.parse(readFileSync(new URL('./fixtures/discovery-preserved.json', import.meta.url), 'utf8'))

for (const entry of ['home', 'direct'] as const) {
  test(`${entry} entry centers the first input and submission docks it for thinking`, async ({ page }, info) => {
    let queries = 0
    await page.route('**/api/v1/**', async route => {
      const path = new URL(route.request().url()).pathname
      if (path === '/api/v1/auth/me') return route.fulfill({ status: 401, json: { error: { code: 'unauthorized', message: '请登录', fields: [] } } })
      if (path === '/api/v1/itineraries') return route.fulfill({ json: { itineraries: [], current_id: null } })
      if (path === '/api/v1/discovery/jobs' && route.request().method() === 'POST') {
        queries++
        return route.fulfill({ json: { id: 'entry-motion' } })
      }
      if (path === '/api/v1/discovery/jobs/entry-motion') return route.fulfill({ json: {
        ...preserved, id: 'entry-motion', status: 'running', intent: 'search', cards: [],
        stage: '正在核实地点', reply: '', request_location: false,
      } })
      return route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'Fixture endpoint not configured.' } } })
    })
    await page.goto(entry === 'home' ? '/' : '/explore')
    if (entry === 'home') await page.getByRole('link', { name: '开始探索' }).click()
    await expect(page.locator('.discovery-workspace')).toHaveAttribute('data-landing', 'true')
    // Finish the page-entry transition before measuring the second transition.
    await page.evaluate(async () => {
      await Promise.all(document.getAnimations().filter(a => a.effect?.getComputedTiming().iterations !== Infinity)
        .map(a => a.finished.catch(() => undefined)))
    })
    const form = page.locator('.discovery-input form')
    const title = await page.getByRole('heading', { name: '想去哪儿？', exact: true }).boundingBox()
    const centered = (await form.boundingBox())!
    const viewport = page.viewportSize()!
    expect(centered.y).toBeGreaterThan(viewport.height * .25)
    expect(centered.y + centered.height).toBeLessThan(viewport.height * .75)
    expect(centered.y - title!.y - title!.height).toBeLessThan(65)
    expect(Math.abs(centered.x + centered.width / 2 - viewport.width / 2)).toBeLessThan(12)
    await expect(page.getByRole('button', { name: '去公园散步' })).toBeVisible()
    await page.screenshot({ path: info.outputPath(`${entry}-centered.png`) })
    const input = page.getByRole('textbox', { name: '继续补充条件' })
    await input.fill('去公园散步')
    await input.press('Enter')
    await expect(page.locator('.discovery-workspace')).toHaveAttribute('data-landing', 'false')
    await expect(page.getByRole('button', { name: '停止查找' })).toBeVisible()
    await expect.poll(() => form.evaluate(node => node.getAnimations().length)).toBeGreaterThan(0)
    await form.evaluate(async node => { await Promise.all(node.getAnimations().map(a => a.finished.catch(() => undefined))) })
    const docked = (await form.boundingBox())!
    expect(docked.y).toBeGreaterThan(centered.y + 60)
    expect(docked.y + docked.height).toBeGreaterThan(viewport.height - 70)
    await expect(page.getByRole('button', { name: '去公园散步' })).toHaveCount(0)
    await expect(page.locator('.discovery-waiting[data-active=true]')).toBeVisible()
    expect(queries).toBe(1)
    await page.screenshot({ path: info.outputPath(`${entry}-thinking.png`) })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width)
  })
}
