import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/client'
import { ItineraryProvider, AddToItinerary } from '../src/features/itineraries/ItineraryProvider'
import { ItineraryCenter } from '../src/features/itineraries/ItineraryCenter'
import type { Itinerary } from '../src/features/itineraries/types'

vi.mock('../src/features/auth/authContext', async original => ({
  ...await original<typeof import('../src/features/auth/authContext')>(), useAuth: () => ({ initializing: false, user: null }),
}))
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })
const trip = (id: string, name: string): Itinerary => ({ id, name, version: 1, created_at: '2026-10-25', updated_at: '2026-10-25',
  start_date: '2026-10-26', end_date: '2026-10-27', travel_mode: 'walking',
  stops: ['甲公园', '乙书店'].map((name, i) => ({ id: String(i), place: { id: String(i), name, city: '苏州', address: '实际地址',
    coordinate: { longitude: 120+i*.01, latitude: 31, system: 'gcj02' }, map_type: '休闲', map_url: '', facts: {} }, added_at: '2026-10-25', experience: '' })),
  days: [{ date: '2026-10-26', stop_ids: ['0', '1'] }, { date: '2026-10-27', stop_ids: [] }],
  unassigned_ids: [], routes: [], route_status: 'ready', weather: {}, notices: [] })

it('adds directly to the latest trip and transfers the just-added stop from its toast', async () => {
  const newest = trip('new', '最近行程'), older = trip('old', '之前行程')
  vi.spyOn(apiClient, 'get').mockResolvedValue({ itineraries: [newest, older], current_id: 'new' })
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async path => path.endsWith('/move')
    ? { itinerary: older } as never : { itinerary: newest, stop_id: 'bound-stop', added: true } as never)
  render(<MemoryRouter><ItineraryProvider><AddToItinerary source={{ favorite_id: 'real-favorite' }} /></ItineraryProvider></MemoryRouter>)
  await userEvent.click(screen.getByRole('button', { name: '加入行程' }))
  await screen.findByText('已加入「最近行程」')
  expect(post).toHaveBeenCalledWith('/itineraries/new/stops', { favorite_id: 'real-favorite' })
  await userEvent.click(screen.getByRole('button', { name: '更换行程' }))
  await userEvent.click(screen.getByRole('button', { name: /之前行程/ }))
  await screen.findByText('已移到「之前行程」')
  expect(post).toHaveBeenCalledWith('/itineraries/new/stops/bound-stop/move', { version: 1, target_id: 'old' })
  expect(post).toHaveBeenCalledTimes(2)
})

it('creates the first itinerary before adding a real source reference', async () => {
  const created = trip('created', '新的出游行程')
  vi.spyOn(apiClient, 'get').mockResolvedValue({ itineraries: [], current_id: null })
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async path => path === '/itineraries'
    ? { itinerary: created } as never : { itinerary: created, stop_id: 'bound', added: true } as never)
  render(<MemoryRouter><ItineraryProvider><AddToItinerary source={{ source_job_id: 'owned-job', place_id: 'real-poi' }} /></ItineraryProvider></MemoryRouter>)
  await userEvent.click(screen.getByRole('button', { name: '加入行程' }))
  await screen.findByRole('dialog', { name: '创建行程' })
  expect(post).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '创建并加入' }))
  await screen.findByText('已加入「新的出游行程」')
  expect(post).toHaveBeenCalledWith('/itineraries/created/stops', { source_job_id: 'owned-job', place_id: 'real-poi' })
})

it('saves a drag without route calls and explicitly updates preserving the edited order', async () => {
  let value = trip('one', '两日行程')
  vi.spyOn(apiClient, 'get').mockImplementation(async () => ({ itineraries: [value], current_id: 'one' }) as never)
  const put = vi.spyOn(apiClient, 'put').mockImplementation(async (_path, body) => {
    value = { ...value, days: (body as Itinerary).days, version: value.version+1, route_status: 'dirty' }
    return { itinerary: value } as never
  })
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async (_path, body) => {
    expect(body).toMatchObject({ version: 2, optimize: false })
    value = { ...value, version: 3, route_status: 'ready' }
    return { itinerary: value } as never
  })
  render(<MemoryRouter initialEntries={['/itineraries/one']}><Routes><Route path='/itineraries/:itineraryId' element={<ItineraryCenter />} /></Routes></MemoryRouter>)
  await screen.findByRole('heading', { name: '两日行程' })
  const dataTransfer = { setData: vi.fn(), effectAllowed: '' }
  fireEvent.dragStart(screen.getByRole('button', { name: '拖动乙书店' }), { dataTransfer })
  fireEvent.dragOver(screen.getByRole('heading', { name: '甲公园' }).closest('article')!, { dataTransfer })
  fireEvent.drop(screen.getByRole('heading', { name: '甲公园' }).closest('article')!, { dataTransfer })
  await screen.findByText('安排已保存 · 路线待更新')
  expect(put).toHaveBeenCalledWith('/itineraries/one/order', expect.objectContaining({
    version: 1, days: [{ date: '2026-10-26', stop_ids: ['1', '0'] }, { date: '2026-10-27', stop_ids: [] }],
  }))
  expect(post).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '更新路线' }))
  await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
  expect(value.days[0].stop_ids).toEqual(['1', '0'])
})

it('saves a transport change without requiring dates or generating routes', async () => {
  let value = { ...trip('one', '待定出游'), start_date: null, end_date: null, days: [], unassigned_ids: ['0', '1'] }
  vi.spyOn(apiClient, 'get').mockImplementation(async () => ({ itineraries: [value], current_id: 'one' }) as never)
  const patch = vi.spyOn(apiClient, 'patch').mockImplementation(async (_path, body) => {
    value = { ...value, ...body as object, version: 2 }; return { itinerary: value } as never
  })
  const post = vi.spyOn(apiClient, 'post')
  render(<MemoryRouter initialEntries={['/itineraries/one']}><Routes><Route path='/itineraries/:itineraryId' element={<ItineraryCenter />} /></Routes></MemoryRouter>)
  await userEvent.click(await screen.findByRole('button', { name: '行程设置' }))
  await userEvent.click(screen.getByRole('radio', { name: '骑行' }))
  await userEvent.click(screen.getByRole('button', { name: '保存设置' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(patch).toHaveBeenCalledWith('/itineraries/one', { version: 1, name: '待定出游', travel_mode: 'bicycling' })
  expect(post).not.toHaveBeenCalled()
})

it('continues an explicit automatic arrangement once using the saved settings revision', async () => {
  let value: Itinerary = { ...trip('one', '两天出游'), start_date: null, end_date: null, days: [], unassigned_ids: ['0', '1'] }
  vi.spyOn(apiClient, 'get').mockImplementation(async () => ({ itineraries: [value], current_id: 'one' }) as never)
  vi.spyOn(apiClient, 'patch').mockImplementation(async (_path, body) => {
    value = { ...value, ...body as object, version: 2 }; return { itinerary: value } as never
  })
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async () => {
    value = { ...value, version: 3, generated_at: '2026-10-25', route_status: 'ready' }; return { itinerary: value } as never
  })
  render(<MemoryRouter initialEntries={['/itineraries/one']}><Routes><Route path='/itineraries/:itineraryId' element={<ItineraryCenter />} /></Routes></MemoryRouter>)
  await userEvent.click(await screen.findByRole('button', { name: '自动安排行程' }))
  fireEvent.change(screen.getByLabelText('出发日期'), { target: { value: '2026-10-26' } })
  expect(screen.getByLabelText('结束日期')).toHaveValue('2026-10-26')
  fireEvent.change(screen.getByLabelText('结束日期'), { target: { value: '2026-10-27' } })
  await userEvent.click(screen.getByRole('radio', { name: '驾车' }))
  await userEvent.click(screen.getByRole('button', { name: '保存并自动安排' }))
  await screen.findByText('路线已更新')
  expect(post).toHaveBeenCalledExactlyOnceWith('/itineraries/one/generate', expect.objectContaining({ version: 2, optimize: true }))
})

it('offers an explicit real-road update inside the map and opens the bound walking segment in AMap', async () => {
  let value = { ...trip('one', '两天出游'), route_status: 'dirty' as Itinerary['route_status'] }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: false }) }))
  vi.spyOn(apiClient, 'get').mockImplementation(async () => ({ itineraries: [value], current_id: 'one' }) as never)
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async () => {
    value = { ...value, version: 2, route_status: 'ready', routes: [{ date: '2026-10-26', from_id: '0', to_id: '1',
      mode: 'walking', actual: true, distance_km: 1.4, duration_minutes: 20, path: [[120,31],[120.005,31.005],[120.01,31]] }] }
    return { itinerary: value } as never
  })
  render(<MemoryRouter initialEntries={['/itineraries/one']}><Routes><Route path='/itineraries/:itineraryId' element={<ItineraryCenter />} /></Routes></MemoryRouter>)
  await screen.findByRole('heading', { name: '两天出游' })
  await userEvent.click(screen.getAllByRole('button', { name: '当天地图' })[0])
  expect(await screen.findByText('顺序已保存 · 路线待更新')).toBeVisible()
  expect(post).not.toHaveBeenCalled()
  const link = screen.getByRole('link', { name: '高德步行导航 1→2' })
  const url = new URL(link.getAttribute('href')!)
  expect(url.origin+url.pathname).toBe('https://uri.amap.com/navigation')
  expect(url.searchParams.get('from')).toBe('120.000000,31.000000,甲公园')
  expect(url.searchParams.get('to')).toBe('120.010000,31.000000,乙书店')
  expect(url.searchParams.get('mode')).toBe('walk')
  expect(url.searchParams.get('coordinate')).toBe('gaode')
  await userEvent.click(screen.getByRole('button', { name: '更新步行路线' }))
  await screen.findByText('步行路线已更新')
  expect(post).toHaveBeenCalledExactlyOnceWith('/itineraries/one/generate', expect.objectContaining({ version: 1, optimize: false }))
})
