import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeAll, expect, it, vi } from 'vitest'
import { apiClient, ApiError } from '../src/api/client'
import { AuthContext } from '../src/features/auth/authContext'
import { CreatePlanControl } from '../src/features/plans/CreatePlanControl'

beforeAll(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true,
    value: function (this: HTMLDialogElement) { this.setAttribute('open', '') } })
})
afterEach(() => vi.restoreAllMocks())
function mount() {
  render(<AuthContext.Provider value={{ user: { username: 'owner' }, initializing: false,
    login: vi.fn(), register: vi.fn(), logout: vi.fn() }}><MemoryRouter>
    <CreatePlanControl historyId='saved' trusted={false} selectedIds={['a', 'b']} city='苏州'
      startDate='2026-10-17' endDate='2026-10-18' originCount={2} onRerun={vi.fn()} />
  </MemoryRouter></AuthContext.Provider>)
}
it('restores plan creation after server confirms ownership of a cached recommendation', async () => {
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ history: { id: 'saved', mode: 'recommendation',
    request: { start_date: '2026-10-17', end_date: '2026-10-18' },
    result: { items: [{ destination: { provider_id: 'a' } }, { destination: { provider_id: 'b' } }] } } })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ plan: { id: 'created' } })
  mount()
  await userEvent.click(screen.getByRole('button', { name: '发起同行计划', exact: true }))
  await userEvent.click(await screen.findByRole('button', { name: '确认创建', exact: true }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/plans', expect.objectContaining({
    history_id: 'saved', candidate_ids: ['a', 'b'],
  })))
  expect(get).toHaveBeenCalledWith('/history/saved')
})
it('does not trust cached history owned by another user', async () => {
  vi.spyOn(apiClient, 'get').mockRejectedValue(new ApiError(404, 'resource_not_found', 'missing'))
  const post = vi.spyOn(apiClient, 'post')
  mount()
  await userEvent.click(screen.getByRole('button', { name: '发起同行计划', exact: true }))
  expect(await screen.findByRole('button', { name: '更新推荐并继续' })).toBeVisible()
  expect(screen.queryByRole('button', { name: '确认创建' })).not.toBeInTheDocument()
  expect(post).not.toHaveBeenCalled()
})
it('does not trust selected IDs absent from the server snapshot', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ history: { id: 'saved', mode: 'recommendation',
    request: { start_date: '2026-10-17', end_date: '2026-10-18' },
    result: { items: [{ destination: { provider_id: 'a' } }] } } })
  mount()
  await userEvent.click(screen.getByRole('button', { name: '发起同行计划', exact: true }))
  expect(await screen.findByRole('button', { name: '更新推荐并继续' })).toBeVisible()
  expect(screen.queryByRole('button', { name: '确认创建' })).not.toBeInTheDocument()
})
