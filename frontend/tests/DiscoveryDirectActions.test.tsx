import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { AuthContext } from '../src/features/auth/authContext'
import { apiClient } from '../src/api/client'
import { DiscoveryPage } from '../src/pages/DiscoveryPage'
import { DiscoveryArchiveCards } from '../src/features/discovery/DiscoveryArchiveCards'
import type { DiscoveryCard, DiscoverySnapshot } from '../src/features/discovery/types'

afterEach(() => vi.restoreAllMocks())
const card = (id: string): DiscoveryCard => ({ place: { id: 'amap:' + id, name: id + '去处', city: '杭州', address: id + '真实地址',
  map_type: '公园;公园', map_url: '', coordinate: { longitude: 120, latitude: 30, system: 'gcj02' },
  facts: { opentime_week: '09:00-18:00', cost: '20' } }, experience: '散步赏秋', reason: '', sources: [], route: null, weather: null })
const cards = [card('one'), card('two')]
function mount() {
  const initial: DiscoverySnapshot = { id: 'owned-job', status: 'completed', stage: '', cards, reply: '', request_location: false,
    center_name: null, source: 'live', context: { origin: null, region: '杭州', max_distance_km: null, start_date: null, end_date: null } }
  return render(<AuthContext.Provider value={{ user: { username: 'isolated_owner' }, initializing: false,
    login: vi.fn(), register: vi.fn(), logout: vi.fn() }}><MemoryRouter initialEntries={['/explore']}><Routes>
    <Route path='/explore' element={<DiscoveryPage initialSnapshot={initial} />} />
    <Route path='/plans/:id' element={<h1>已创建的计划</h1>} />
  </Routes></MemoryRouter></AuthContext.Provider>)
}

it('creates directly from selected real IDs and explicit dates without an assistant request', async () => {
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async path => {
    if (path === '/discovery/jobs/owned-job/history') return { history_id: 'owned-history' } as never
    if (path === '/plans') return { plan: { id: 'new-plan' } } as never
    throw new Error('Unexpected model or business request: ' + path)
  })
  mount()
  await userEvent.click(screen.getAllByRole('button', { name: '加入比较' })[0])
  await userEvent.click(screen.getAllByRole('button', { name: '加入比较' })[0])
  await userEvent.click(screen.getByRole('button', { name: '发起同行计划' }))
  const dialog = await screen.findByRole('dialog', { name: '创建同行计划' })
  expect(post.mock.calls.filter(([p]) => p === '/plans')).toHaveLength(0)
  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1)
  const date = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`
  fireEvent.change(within(dialog).getByLabelText('出发日期'), { target: { value: date } })
  fireEvent.change(within(dialog).getByLabelText('结束日期'), { target: { value: date } })
  await userEvent.click(within(dialog).getByRole('button', { name: '确认创建' }))
  await screen.findByRole('heading', { name: '已创建的计划' })
  expect(post).toHaveBeenCalledWith('/plans', { history_id: 'owned-history', candidate_ids: ['amap:one', 'amap:two'],
    name: '一起出游', expected_count: 2, start_date: date, end_date: date })
  expect(post.mock.calls.filter(([p]) => p.endsWith('/history'))).toHaveLength(1)
  expect(post.mock.calls.some(([p]) => p.includes('/assistant/') || p === '/discovery/jobs')).toBe(false)
})

it('compares available visiting facts and favorites the bound place through the existing API', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ favorites: [] })
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async path => path.endsWith('/history')
    ? { history_id: 'history' } as never : { favorite: { id: 'saved' } } as never)
  mount()
  await userEvent.click(screen.getAllByRole('button', { name: '加入比较' })[0])
  await userEvent.click(screen.getAllByRole('button', { name: '加入比较' })[0])
  await userEvent.click(screen.getByRole('button', { name: '查看对比' }))
  const comparison = await screen.findByRole('dialog', { name: '地点对比' })
  expect(within(comparison).getByRole('rowheader', { name: '开放时间' })).toBeInTheDocument()
  expect(within(comparison).getAllByRole('cell', { name: '¥20 / 人' })).toHaveLength(2)
  await userEvent.click(within(comparison).getAllByRole('button', { name: '查看详情' })[0])
  const detail = await screen.findByRole('dialog', { name: 'one去处详情' })
  await userEvent.click(within(detail).getByRole('button', { name: '收藏地点' }))
  await waitFor(() => expect(within(detail).getByRole('button', { name: '已收藏' })).toHaveAttribute('aria-pressed', 'true'))
  expect(post).toHaveBeenCalledWith('/favorites', expect.objectContaining({ provider: 'amap', destination: expect.objectContaining({ provider_id: 'one', name: 'one去处' }) }))
  expect(post.mock.calls.some(([p]) => p.includes('/assistant/'))).toBe(false)
})

it('favorites directly from a card, shares its initial lookup, and synchronizes an undo in detail', async () => {
  let saved = false
  const get = vi.spyOn(apiClient, 'get').mockImplementation(async () => ({ favorites: saved
    ? [{ id: 'card-saved', place: { provider: 'amap', provider_place_id: 'one' } }] : [] }) as never)
  const post = vi.spyOn(apiClient, 'post').mockImplementation(async path => {
    if (path.endsWith('/history')) return { history_id: 'history' } as never
    saved = true; return { favorite: { id: 'card-saved' } } as never
  })
  const remove = vi.spyOn(apiClient, 'delete').mockImplementation(async () => { saved = false })
  mount()
  await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
  const favorite = screen.getByRole('button', { name: '收藏one去处' })
  await userEvent.click(favorite)
  await waitFor(() => expect(favorite).toHaveAttribute('aria-pressed', 'true'))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '了解one去处' }))
  const detail = await screen.findByRole('dialog', { name: 'one去处详情' })
  await userEvent.click(await within(detail).findByRole('button', { name: '已收藏' }))
  await waitFor(() => expect(favorite).toHaveAttribute('aria-pressed', 'false'))
  expect(remove).toHaveBeenCalledWith('/favorites/card-saved')
  expect(post.mock.calls.some(([path]) => path.includes('/assistant/') || path === '/discovery/jobs')).toBe(false)
})

it('makes public cards actionable without inventing private facts or showing reasons', async () => {
  render(<MemoryRouter><DiscoveryArchiveCards snapshot={{ schema_version: 'discovery-v1', mode: 'discovery', city: '杭州',
    start_date: null, end_date: null, generated_at: '', cards: cards.map(c => ({ place: c.place, experience: c.experience,
      reason: '不显示的推荐理由', sources: [], weather: null })) }} /></MemoryRouter>)
  expect(screen.queryByText('不显示的推荐理由')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '了解one去处' }))
  const dialog = screen.getByRole('dialog', { name: 'one去处详情' })
  expect(within(dialog).getByRole('link', { name: '查看位置 ↗' }).getAttribute('href')).toContain('uri.amap.com/search')
  expect(within(dialog).getByRole('link', { name: '继续探索' })).toHaveAttribute('href', '/explore')
})

it('refreshes mounted favorite stars after a chat business operation', async () => {
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ favorites: [] })
  mount()
  await waitFor(() => expect(get).toHaveBeenCalledWith('/favorites'))
  await new Promise(resolve => setTimeout(resolve, 0))
  get.mockResolvedValue({ favorites: [{ id: 'chat-saved', place: { provider: 'amap', provider_place_id: 'two' } }] })
  window.dispatchEvent(new Event('roambot.business-changed'))
  await waitFor(() => expect(screen.getByRole('button', { name: '取消收藏two去处' })).toHaveAttribute('aria-pressed', 'true'))
  expect(screen.getByRole('button', { name: '收藏one去处' })).toHaveAttribute('aria-pressed', 'false')
})

it('opens every recommended place on the map and switches focus without another search', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ favorites: [] })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ history_id: 'owned-history' })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: false }) }))
  try {
    mount()
    await userEvent.click(screen.getByRole('button', { name: '了解one去处' }))
    await userEvent.click(screen.getByRole('button', { name: '查看位置', exact: true }))
    const map = await screen.findByRole('dialog', { name: '景点位置' })
    expect(within(map).getByRole('button', { name: 'one去处', exact: true })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(map).getByRole('button', { name: 'two去处', exact: true }))
    expect(within(map).getByRole('button', { name: 'two去处', exact: true })).toHaveAttribute('aria-pressed', 'true')
    expect(within(map).getByRole('button', { name: 'one去处', exact: true })).toHaveAttribute('aria-pressed', 'false')
    expect(post.mock.calls.every(([path]) => path === '/discovery/jobs/owned-job/history')).toBe(true)
  } finally { vi.unstubAllGlobals() }
})
