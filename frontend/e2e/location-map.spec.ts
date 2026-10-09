import { expect, test } from '@playwright/test'
import { submitRecommendation } from './helpers'

test('map loads only after opening, switches candidates, and closes without navigating', async ({ page }, info) => {
  let sdkCalls = 0
  await page.route('**/api/v1/maps/config', route => route.fulfill({ json: {
    enabled: true, key: 'browser-fixture', service_host: '/api/v1/maps/_AMapService',
  } }))
  // External SDK boundary fixture, not a screenshot of actual highder map tiles.
  await page.route('https://webapi.amap.com/maps?**', route => {
    sdkCalls++
    return route.fulfill({ contentType: 'application/javascript', body: `
      window.AMap = {
        Map: class {
          constructor(el, opts) { this.el=el; this.el.style.background='#e8f3f6'; this.el.dataset.center=opts.center.join(','); }
          add(markers) { markers.forEach(marker => this.el.append(marker.content)); }
          on(event, cb) { if(event==='complete') setTimeout(cb, 0); }
          setFitView() {}
          setZoomAndCenter(zoom, point) { this.el.dataset.center=point.join(','); }
          destroy() { this.el.replaceChildren(); }
        },
        Marker: class { constructor(opts) { this.content=opts.content; this.content.dataset.position=opts.position.join(','); } }
      };
    ` })
  })
  await page.route('**/api/v1/recommendations', async route => {
    const response = await route.fetch()
    const data = await response.json()
    const first = data.items[0]
    first.destination.provider_id = 'amap:B01234'
    data.items.push({ ...first, destination: { ...first.destination, provider_id: 'amap:B05678',
      name: '另一候选景点', coordinate: { longitude: 120.8, latitude: 31.4, system: 'gcj02' } } })
    await route.fulfill({ response, json: data })
  })
  await page.goto('/recommend')
  await submitRecommendation(page)
  expect(sdkCalls).toBe(0)
  const originalUrl = page.url()
  await page.getByRole('button', { name: '查看位置', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '景点位置' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('正在加载地图…')).toHaveCount(0)
  expect(sdkCalls).toBe(1)
  await dialog.getByRole('button', { name: '另一候选景点', exact: true }).click()
  await expect(dialog.locator('.location-map')).toHaveAttribute('data-center', '120.8,31.4')
  await expect(dialog.locator('.location-footer strong')).toHaveText('另一候选景点')
  const external = new URL((await dialog.getByRole('link', { name: '打开高德' }).getAttribute('href'))!)
  expect(external.searchParams.get('keyword')).toBe('另一候选景点')
  expect(external.searchParams.get('city')).toBe('苏州')
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
  const heading = dialog.getByRole('heading', { name: '景点位置' })
  expect(await heading.evaluate(el => {
    const rect = el.getBoundingClientRect()
    return document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)?.closest('.location-dialog') !== null
  })).toBe(true)
  await page.screenshot({ path: `../evidence/location-map-fixture-${info.project.name}-20261009.png` })
  await dialog.getByRole('button', { name: '关闭地图' }).click()
  await expect(dialog).toHaveCount(0)
  expect(page.url()).toBe(originalUrl)
  await expect(page.getByRole('button', { name: '查看位置' })).toBeFocused()
  await page.getByRole('button', { name: '查看位置' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  expect(sdkCalls).toBe(1)
})

test('unconfigured map reports its state and never requests the SDK', async ({ page }) => {
  await page.route('**/api/v1/maps/config', route => route.fulfill({ json: { enabled: false } }))
  let calls = 0
  await page.route('https://webapi.amap.com/**', route => { calls++; return route.abort() })
  await page.goto('/recommend')
  await submitRecommendation(page)
  await page.getByRole('button', { name: '查看位置' }).click()
  await expect(page.getByText('地图暂未配置，请稍后再试')).toBeVisible()
  await page.getByRole('button', { name: '重试加载' }).click()
  await expect(page.getByText('地图暂未配置，请稍后再试')).toBeVisible()
  expect(calls).toBe(0)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})
