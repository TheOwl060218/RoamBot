import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { LocationMapDialog } from '../src/features/search/LocationMapDialog'
import type { RecommendationItem } from '../src/api/types'
import { BusinessAssistantContext } from '../src/features/commands/commandContext'
import { CommandBridge } from '../src/features/commands/commandBridge'

function resultItem(): RecommendationItem {
  return {
    destination: { provider_id: 'first', name: '金鸡湖', city: '苏州', address: '工业园区',
      coordinate: { longitude: 120.7, latitude: 31.3, system: 'gcj02' }, type_name: '湖景',
      type_code: '110000', scenery_tags: ['lake'], rating: 4.8, popularity_rank: 1 },
    distances: [], weather: [], daily_suitability: [],
    group_accessibility: { average_distance_km: 0, max_distance_km: 0, distance_variance: 0,
      distance_stddev: 0, fairness_score: 100 },
    score: { weather: 90, distance: 80, fairness: 100, popularity: 90, coverage_penalty: 0, total: 85 },
    explanation: '', overall_advice: 'suitable',
  }
}

afterEach(() => vi.unstubAllGlobals())

it('draws numbered itinerary markers with separate actual and indicative route styles', async () => {
  const line = vi.fn(), marker = vi.fn(), mapOptions = vi.fn(), baseLayer = vi.fn()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: true, key: 'fixture', service_host: '/fixture' }) }))
  vi.stubGlobal('AMap', { Map: class {
    constructor(_element: HTMLElement, options: object) { mapOptions(options) }
    add() {} destroy() {} setZoomAndCenter() {} setFitView() {}
    on(_name: string, callback: () => void) { queueMicrotask(callback) }
  }, Marker: class { constructor(options: unknown) { marker(options) } },
    Polyline: class { constructor(options: unknown) { line(options) } },
    TileLayer: class { constructor(options: unknown) { baseLayer(options) } } })
  const first = resultItem(), second = { ...first, destination: { ...first.destination, provider_id: 'next', name: '下一站' } }
  render(<LocationMapDialog items={[first, second]} selectedId='first' onClose={() => {}} numbered title='当天路线'
    lines={[{ path: [[120,31],[120.1,31.1]], actual: true }, { path: [[120.1,31.1],[120.2,31.2]], actual: false }]} />)
  await waitFor(() => expect(line).toHaveBeenCalledTimes(2))
  expect(mapOptions).toHaveBeenCalledWith(expect.objectContaining({ mapStyle: 'amap://styles/normal', layers: expect.any(Array) }))
  expect(baseLayer).toHaveBeenCalledWith({ opacity: .68 })
  expect(line.mock.calls[0][0]).toMatchObject({ strokeStyle: 'solid', showDir: true, isOutline: true, outlineColor: '#ffffff' })
  expect(line.mock.calls[1][0]).toMatchObject({ strokeStyle: 'dashed', showDir: false })
  expect(marker.mock.calls[0][0]).toMatchObject({ position: [120.7,31.3], anchor: 'bottom-center' })
  expect(marker.mock.calls[0][0].content.textContent).toBe('1')
  expect(marker.mock.calls[0][0].content.getAttribute('aria-label')).toBe('选择金鸡湖')
  expect(screen.getByRole('heading', { name: '当天路线' })).toBeInTheDocument()
})

it('routes zoom, pan and reset commands to the configured map instance', async () => {
  const zoom = vi.fn(), fit = vi.fn()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () =>
    ({ enabled: true, key: 'fixture-map', service_host: '/fixture-proxy' }) }))
  vi.stubGlobal('AMap', { Map: class {
    add() {} destroy() {} setZoomAndCenter = zoom; setFitView = fit
    on(_name: string, callback: () => void) { queueMicrotask(callback) }
  }, Marker: class {} })
  const bridge = new CommandBridge()
  const item = resultItem()
  render(<BusinessAssistantContext.Provider value={{ bridge, send: vi.fn(), busy: false }}>
    <LocationMapDialog items={[item]} selectedId='first' onClose={() => {}} />
  </BusinessAssistantContext.Provider>)
  await waitFor(() => expect(zoom).toHaveBeenCalledWith(13, [120.7, 31.3]))
  await act(() => bridge.perform({ tool: 'control_map', arguments: { action: 'zoom_in' } }))
  expect(zoom).toHaveBeenLastCalledWith(14, [120.7, 31.3])
  await act(() => bridge.perform({ tool: 'control_map', arguments: { action: 'left' } }))
  expect(zoom.mock.calls.at(-1)?.[1][0]).toBeLessThan(120.7)
  await act(() => bridge.perform({ tool: 'control_map', arguments: { action: 'reset' } }))
  expect(fit).toHaveBeenCalledTimes(2)
})

it('reports missing configuration, keeps candidates usable and retries', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: false }) })
  vi.stubGlobal('fetch', fetcher)
  const first = resultItem()
  const second = { ...first, destination: { ...first.destination, provider_id: 'second', name: '另一景点' } }
  const select = vi.fn()
  render(<LocationMapDialog items={[first, second]} selectedId={first.destination.provider_id} onSelect={select} onClose={() => {}} />)
  await expect(screen.findByText('地图暂未配置，请稍后再试')).resolves.toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '2 · 另一景点' }))
  expect(select).toHaveBeenCalledWith(second)
  fireEvent.click(screen.getByRole('button', { name: '重试加载' }))
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
  expect(document.querySelector('script[src*="webapi.amap.com"]')).toBeNull()
})

it('fits all markers initially, focuses on selection and returns to overview without recreating the map', async () => {
  const zoom = vi.fn(), fit = vi.fn(), created = vi.fn(), marker = vi.fn()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: true, key: 'fixture', service_host: '/fixture' }) }))
  vi.stubGlobal('AMap', { Map: class {
    constructor() { created() }
    add() {} destroy() {} setZoomAndCenter = zoom; setFitView = fit
    on(_name: string, callback: () => void) { queueMicrotask(callback) }
  }, Marker: class { constructor(options: unknown) { marker(options) } } })
  const first = resultItem(), second = { ...first, destination: { ...first.destination, provider_id: 'second', name: '另一景点', coordinate: { longitude: 120.8, latitude: 31.4, system: 'gcj02' as const } } }
  const items = [first, second], select = vi.fn(), close = vi.fn()
  const view = render(<LocationMapDialog items={items} selectedId='first' onSelect={select} onClose={close} />)
  await waitFor(() => expect(fit).toHaveBeenCalledTimes(1))
  expect(marker).toHaveBeenCalledTimes(2)
  expect(zoom).not.toHaveBeenCalled()
  fireEvent.click(marker.mock.calls[1][0].content)
  expect(select).toHaveBeenCalledWith(second)
  view.rerender(<LocationMapDialog items={items} selectedId='second' onSelect={select} onClose={close} />)
  await waitFor(() => expect(zoom).toHaveBeenCalledWith(13, [120.8, 31.4]))
  expect(marker.mock.calls[1][0].content.getAttribute('aria-pressed')).toBe('true')
  fireEvent.click(screen.getByRole('button', { name: '查看全部地点' }))
  expect(fit).toHaveBeenCalledTimes(2)
  expect(created).toHaveBeenCalledTimes(1)
})

it('shows pin names on hover and focus, restores the selected name and keeps long names inside map edges', async () => {
  const markers: HTMLElement[] = []
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: true, key: 'fixture', service_host: '/fixture' }) }))
  vi.stubGlobal('AMap', { Map: class {
    constructor(private element: HTMLElement) {
      element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 320, height: 240 }) as DOMRect
    }
    add() {} destroy() {} setZoomAndCenter() {} setFitView() {}
    on(name: string, callback: () => void) { if (name === 'complete') queueMicrotask(callback) }
  }, Marker: class { constructor({ content }: { content: HTMLElement }) {
    content.getBoundingClientRect = () => ({ left: 286, top: 4, width: 36, height: 46 }) as DOMRect
    markers.push(content)
  } } })
  const first = resultItem(), second = { ...first, destination: { ...first.destination, provider_id: 'second', name: '另一处很长名称的景点' } }
  render(<LocationMapDialog items={[first, second]} selectedId='first' onClose={() => {}} />)
  await waitFor(() => expect(document.querySelector('.location-marker-name')).toHaveTextContent('金鸡湖'))
  fireEvent.mouseEnter(markers[1])
  const label = document.querySelector<HTMLElement>('.location-marker-name')!
  expect(label).toHaveTextContent('另一处很长名称的景点')
  Object.defineProperties(label, { offsetWidth: { value: 190 }, offsetHeight: { value: 36 } })
  fireEvent.mouseLeave(markers[1])
  fireEvent.focus(markers[1])
  expect(label).toHaveTextContent('另一处很长名称的景点')
  expect(parseFloat(label.style.left)).toBeLessThanOrEqual(122)
  expect(parseFloat(label.style.top)).toBeGreaterThanOrEqual(8)
  expect(parseFloat(label.style.top) + 36).toBeLessThanOrEqual(232)
  fireEvent.blur(markers[1])
  expect(label).toHaveTextContent('金鸡湖')
  expect(markers[1]).not.toHaveAttribute('title')
})
