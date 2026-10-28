import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

const preserved = JSON.parse(readFileSync(new URL('./fixtures/discovery-preserved.json', import.meta.url), 'utf8'))

test('failed replacement keeps usable cards and follow-up keeps the latest query context', async ({ page }, testInfo) => {
  const requests: Record<string, unknown>[] = []
  let failed = false, pendingPolls = 0
  const firstName = preserved.cards[0].place.name as string
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname
    if (path === '/api/v1/auth/me') return route.fulfill({ json: { user: { username: 'isolated_maintenance' }, csrf_token: 'mock-csrf' } })
    if (path === '/api/v1/itineraries') return route.fulfill({ json: { itineraries: [], current_id: null } })
    if (path === '/api/v1/discovery/jobs' && request.method() === 'POST') {
      requests.push(request.postDataJSON())
      return route.fulfill({ json: { id: `maintenance-${requests.length}` } })
    }
    if (path.endsWith('/history')) return route.fulfill({ json: { history_id: 'mock-owned-history' } })
    if (path === '/api/v1/discovery/jobs/maintenance-1') return route.fulfill({ json: {
      ...preserved, id: 'maintenance-1', intent: 'search', status: 'completed', display_title: '原来的散步安排',
    } })
    if (path === '/api/v1/discovery/jobs/maintenance-2') {
      pendingPolls++
      return route.fulfill({ json: { ...preserved, id: 'maintenance-2', intent: 'search', cards: [],
        status: failed ? 'failed' : 'running', stage: failed ? '' : '正在核实地点',
        reply: failed ? '这轮查询尚未完成。' : '', request_location: false } })
    }
    if (path === '/api/v1/discovery/jobs/maintenance-3') return route.fulfill({ json: {
      ...preserved, id: 'maintenance-3', intent: 'search', status: 'completed', display_title: '新的杭州安排',
      cards: [{ ...preserved.cards[0], place: { ...preserved.cards[0].place, id: 'amap:mock-new', name: '新的杭州地点' } }],
    } })
    return route.fulfill({ status: 404, json: { error: { code: 'not_found', message: 'Mock endpoint not configured.' } } })
  })
  await page.goto('/explore')
  const input = page.getByRole('textbox', { name: '继续补充条件' })
  await input.fill('苏州散步'); await input.press('Enter')
  const oldHeading = page.getByRole('heading', { name: firstName, exact: true })
  await expect(oldHeading).toBeVisible()
  await expect(page.getByRole('button', { name: '重新加载推荐', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '停止查找' })).toHaveCount(0)
  await oldHeading.evaluate(node => node.setAttribute('data-maintenance-kept', 'yes'))
  await input.fill('换成杭州'); await input.press('Enter')
  await expect.poll(() => pendingPolls).toBeGreaterThan(0)
  await expect(oldHeading).toHaveAttribute('data-maintenance-kept', 'yes')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('原来的散步安排')
  failed = true
  await expect(page.getByText('这轮查询尚未完成。', { exact: true })).toBeVisible()
  await expect(oldHeading).toHaveAttribute('data-maintenance-kept', 'yes')
  await expect(page.getByRole('button', { name: '换一批', exact: true })).toBeEnabled()
  await input.fill('继续刚才的杭州'); await input.press('Enter')
  await expect(page.getByRole('heading', { name: '新的杭州地点', exact: true })).toBeVisible()
  expect(requests[2]).toMatchObject({ previous_id: 'maintenance-2' })
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('新的杭州安排')
  await expect(oldHeading).toHaveCount(0)
  await expect(page.getByRole('button', { name: '重新加载推荐', exact: true })).toHaveCount(0)
  await page.locator('.route-content').evaluate(async node => {
    await Promise.all(node.getAnimations({ subtree: true }).filter(animation => animation.effect?.getComputedTiming().iterations !== Infinity)
      .map(animation => animation.finished.catch(() => undefined)))
  })
  await page.screenshot({ path: testInfo.outputPath('recovered-result.png') })
})
