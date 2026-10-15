import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { apiClient, ApiError } from '../src/api/client'
import { FavoriteDetail } from '../src/features/favorites/FavoriteDetail'
import { PlansPage } from '../src/features/plans/PlanPages'
import { AuthContext } from '../src/features/auth/authContext'
import { HistoryPage } from '../src/pages/HistoryPage'

function Destination() { const l = useLocation(); return <output aria-label="跳转结果">{JSON.stringify({ path: l.pathname, state: l.state })}</output> }
afterEach(() => vi.restoreAllMocks())

it('shows the date action returned for an expired history rerun', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ histories: [{ id: 'expired', mode: 'recommendation',
    city: '苏州', start_date: '2026-01-01', end_date: '2026-01-02', item_count: 2,
    created_at: '2026-01-01' }] })
  vi.spyOn(apiClient, 'post').mockRejectedValue(new ApiError(422, 'history_dates_expired', '请选择新的出行日期。'))
  render(<AuthContext.Provider value={{ user: { username: 'owner' }, initializing: false,
    login: vi.fn(), register: vi.fn(), logout: vi.fn() }}><MemoryRouter><HistoryPage /></MemoryRouter></AuthContext.Provider>)
  await userEvent.click(await screen.findByRole('button', { name: '更多历史操作' }))
  await userEvent.click(screen.getByRole('button', { name: '重新查询', exact: true }))
  expect(await screen.findByRole('status')).toHaveTextContent('请选择新的出行日期。')
})

it('sends a favorite evaluation to the query page while preserving its target', async () => {
  render(<MemoryRouter><FavoriteDetail favorite={{ id: 'favorite', created_at: '2026-10-08', place: {
    provider_id: 'poi', name: '西湖', address: '西湖入口', city: '杭州', type_name: '湖景', type_code: '110000',
    coordinate: { longitude: 120, latitude: 30, system: 'gcj02' }, scenery_tags: ['lake'], popularity_rank: 1, rating: 4.8,
  } }} onDelete={() => undefined} /><Destination /></MemoryRouter>)
  await userEvent.setup().click(screen.getByRole('link', { name: '重新评估' }))
  expect(screen.getByLabelText('跳转结果')).toHaveTextContent('"path":"/recommend"')
  expect(screen.getByLabelText('跳转结果')).toHaveTextContent('"evaluationTarget":"西湖"')
})

it('starts a recommendation from plans without navigating to the photo homepage', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plans: [] })
  render(<MemoryRouter><PlansPage /><Destination /></MemoryRouter>)
  await userEvent.setup().click(screen.getByRole('link', { name: '发起同行计划' }))
  expect(screen.getByLabelText('跳转结果')).toHaveTextContent('"path":"/recommend"')
  expect(screen.getByLabelText('跳转结果')).toHaveTextContent('"startTeamPick":true')
})

it('returns a history rerun to the query page with its restored draft and result', async () => {
  const summary = { id: 'history', mode: 'recommendation', city: '杭州', start_date: '2026-12-01', end_date: '2026-12-02', created_at: '2026-10-08', item_count: 0 }
  vi.spyOn(apiClient, 'get').mockResolvedValue({ histories: [summary] })
  vi.spyOn(apiClient, 'post').mockResolvedValue({ history: { ...summary, snapshot: true,
    request: { city: '杭州', main_origin: '杭州东站', companion_origins: [], max_distance_km: 50,
      start_date: '2026-12-01', end_date: '2026-12-02', scenery_types: [], scenery_match_mode: 'any',
      weights: { weather: 40, distance: 30, popularity: 30, fairness: 0 } },
    result: { items: [], source_state: { kind: 'demo', notices: [] }, generated_at: '2026-10-08', uncovered_scenery_types: [] },
  } })
  render(<AuthContext.Provider value={{ user: { id: 'owner', username: 'alice' }, initializing: false,
    login: async () => undefined, register: async () => undefined, logout: async () => undefined }}>
    <MemoryRouter><HistoryPage /><Destination /></MemoryRouter>
  </AuthContext.Provider>)
  await userEvent.setup().click(await screen.findByRole('button', { name: '更多历史操作' }))
  await userEvent.setup().click(screen.getByRole('button', { name: '重新查询', exact: true }))
  await waitFor(() => expect(screen.getByLabelText('跳转结果')).toHaveTextContent('"path":"/recommend"'))
  expect(screen.getByLabelText('跳转结果')).toHaveTextContent('杭州东站')
  expect(screen.getByLabelText('跳转结果')).toHaveTextContent('"history_id":"history"')
})
