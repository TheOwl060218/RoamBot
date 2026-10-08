import { expect, test, type Page } from '@playwright/test'

async function personalFixtures(page: Page) {
  const place = (name: string, id: string) => ({ provider_id: id, name, address: `${name}入口`, city: '苏州',
    coordinate: { longitude: 120.5, latitude: 31.3, system: 'gcj02' }, type_name: '山岳景区', type_code: '110200',
    scenery_tags: ['mountain'], popularity_rank: 1, rating: 4.6 })
  let favorites = [
    { id: 'style-a', place: place('穹窿山', 'poi-a'), created_at: '2026-10-06T00:00:00Z' },
    { id: 'style-b', place: place('天平山', 'poi-b'), created_at: '2026-10-06T00:00:00Z' },
  ]
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    if (route.request().method() === 'DELETE' && url.pathname.includes('/favorites/')) {
      favorites = favorites.filter(favorite => !url.pathname.endsWith(favorite.id))
      await route.fulfill({ status: 204 })
      return
    }
    const body = url.pathname.endsWith('/auth/me')
      ? { user: { id: 'style-user', username: 'fixture' }, csrf_token: 'fixture' }
      : url.pathname.endsWith('/favorites') ? { favorites }
        : url.pathname.endsWith('/plans') ? { plans: [] }
          : url.pathname.endsWith('/history') ? { histories: [{ id: 'style-history', mode: 'recommendation', city: '苏州',
            start_date: '2026-12-01', end_date: '2026-12-02', created_at: '2026-10-06T00:00:00Z', item_count: 2 }] }
            : {}
    await route.fulfill({ json: body })
  })
}

test('favorite surfaces match recommendation rounding and selection stays usable', async ({ page }, info) => {
  await personalFixtures(page)
  await page.goto('/recommend')
  const reference = page.locator('.sample-scene-card').first()
  await expect(reference).toBeAttached()
  const radius = await reference.evaluate(element => getComputedStyle(element).borderTopLeftRadius)
  await page.goto('/favorites')
  const selected = page.getByRole('button', { name: '查看 穹窿山', exact: true })
  await expect(selected).toHaveAttribute('aria-pressed', 'true')
  await expect(selected).toHaveCSS('border-radius', '10px')
  await expect(page.locator('.favorite-detail')).toHaveCSS('border-radius', radius)
  await expect(page.locator('.favorite-detail')).toHaveCSS('background-color', 'rgb(255, 255, 255)')
  const border = await selected.evaluate(element => getComputedStyle(element).borderTopColor)
  expect(border).not.toBe('rgb(23, 111, 138)')
  await page.getByRole('button', { name: '查看 天平山', exact: true }).click()
  await expect(page.locator('.favorite-detail h2')).toHaveText('天平山')
  await expect(page.getByRole('button', { name: '查看 天平山', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.screenshot({ path: `../evidence/favorites-style-${info.project.name}-20261008.png`, fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.getByRole('button', { name: '删除 天平山', exact: true }).click()
  await expect(page.locator('.favorite-detail h2')).toHaveText('穹窿山')
})

test('history cards and secondary menu do not lose their rounded borders', async ({ page }, info) => {
  await personalFixtures(page)
  await page.goto('/history')
  await expect(page.locator('.history-row')).toHaveCSS('border-radius', '16px')
  await page.getByRole('button', { name: '更多历史操作' }).click()
  await page.getByRole('button', { name: '更多操作', exact: true }).click()
  await expect(page.locator('.history-menu-more-panel')).toBeVisible()
  await expect(page.locator('.history-menu-more-panel')).toHaveCSS('border-radius', '10px')
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: `../evidence/history-style-${info.project.name}-20261008.png`, fullPage: true })
  await page.keyboard.press('Escape')
  await expect(page.getByRole('toolbar', { name: '历史快捷操作' })).toBeHidden()
})
