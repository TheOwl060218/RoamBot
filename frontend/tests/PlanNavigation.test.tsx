import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { apiClient } from '../src/api/client'
import { AuthContext } from '../src/features/auth/authContext'
import { PlanNavigation } from '../src/features/plans/PlanNavigation'
import type { TravelPlan } from '../src/api/types'

function view() {
  render(<AuthContext.Provider value={{ user: { username: 'owner' }, initializing: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}><MemoryRouter><PlanNavigation /></MemoryRouter></AuthContext.Provider>)
}
afterEach(() => vi.restoreAllMocks())
test('closed active plan is labeled pending decision rather than voting', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plans: [{ id: 'closed', city: '苏州', start_date: '2026-12-12', end_date: '2026-12-12', ended: false, status: 'closed', expected_count: 2, summary: { voted_count: 1 }, candidates: [] }] })
  view()
  expect(await screen.findByRole('link', { name: /计划中心：苏州.*待决定/ })).toHaveAttribute('href', '/plans/closed')
})
test('plain plan center is present without any active plan', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plans: [] })
  view()
  expect(await screen.findByRole('link', { name: '计划中心' })).toHaveAttribute('href', '/plans')
})
test('nearest active plan appears while ended plans stay out of the header', async () => {
  const create = (id: string, start: string, ended: boolean) => ({ id, name: id, city: '苏州', start_date: start, end_date: start, ended, status: 'voting', expected_count: 2, summary: { voted_count: 1 }, candidates: [] }) as TravelPlan
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plans: [create('ended', '2026-01-01', true), create('later', '2026-12-12', false), create('nearest', '2026-10-10', false)] })
  view()
  expect(await screen.findByRole('link', { name: /计划中心：苏州/ })).toHaveAttribute('href', '/plans/nearest')
  expect(screen.queryByText('ended')).not.toBeInTheDocument()
})
