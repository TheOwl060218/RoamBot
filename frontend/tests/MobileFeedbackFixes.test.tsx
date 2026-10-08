import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useState } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { AppShell } from '../src/app/AppShell'
import { AuthContext } from '../src/features/auth/authContext'
import { CreatePlanControl } from '../src/features/plans/CreatePlanControl'
import { apiClient } from '../src/api/client'

it('lets people clear the count and validates inside the plan form instead of browser bubbles', async () => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ plan: { id: 'saved' } })
  render(<AuthContext.Provider value={{ user: { username: 'owner' }, initializing: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter><CreatePlanControl historyId='fixture' trusted selectedIds={['a', 'b']} city='苏州' startDate='2026-12-01' endDate='2026-12-01' originCount={2} onRerun={vi.fn()} /></MemoryRouter>
  </AuthContext.Provider>)
  fireEvent.click(screen.getByRole('button', { name: '创建同行计划' }))
  const form = screen.getByRole('dialog').querySelector('form')!
  const count = screen.getByLabelText('预计同行人数')
  fireEvent.change(count, { target: { value: '' } })
  expect(count).toHaveValue(null)
  expect(form.noValidate).toBe(true)
  fireEvent.submit(form)
  expect(screen.getByRole('alert')).toHaveTextContent(/1.*100/)
  expect(post).not.toHaveBeenCalled()
  fireEvent.change(count, { target: { value: '3' } })
  fireEvent.submit(form)
  await waitFor(() => expect(post).toHaveBeenCalledWith('/plans', expect.objectContaining({ expected_count: 3 })))
  vi.restoreAllMocks()
})

function Path() { const location = useLocation(); return <output aria-label='当前位置'>{location.pathname}</output> }
function Guest() {
  const [user, setUser] = useState<{ username: string } | null>(null)
  return <AuthContext.Provider value={{ user, initializing: false, login: async () => { setUser({ username: 'fixture' }) }, register: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={['/recommend']}><AppShell><p>查询内容</p><Path /></AppShell></MemoryRouter>
  </AuthContext.Provider>
}
it('opens plan authentication before leaving the current page and navigates only after login', async () => {
  render(<Guest />)
  fireEvent.click(screen.getByRole('link', { name: '计划中心', exact: true }))
  expect(screen.getByLabelText('当前位置')).toHaveTextContent('/recommend')
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '关闭', exact: true }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByLabelText('当前位置')).toHaveTextContent('/recommend')
  fireEvent.click(screen.getByRole('link', { name: '计划中心', exact: true }))
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'fixture' } })
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'Fixture123!' } })
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '登录', exact: true }))
  await waitFor(() => expect(screen.getByLabelText('当前位置')).toHaveTextContent('/plans'))
})
