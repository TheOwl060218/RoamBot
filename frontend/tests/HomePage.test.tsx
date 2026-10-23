import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '../src/features/auth/authContext'
import { HomePage } from '../src/pages/HomePage'

function Location() { const location = useLocation(); return <output aria-label="路径">{location.pathname}</output> }
function mount(options: Partial<AuthContextValue> = {}) {
  function Harness() {
    const [user, setUser] = useState(options.user ?? null)
    const value: AuthContextValue = {
      user, initializing: options.initializing ?? false,
      login: async () => { setUser({ id: 'home-user', username: 'alice' }) },
      register: async () => { setUser({ id: 'home-user', username: 'alice' }) },
      logout: options.logout ?? (async () => { setUser(null) }),
    }
    return <AuthContext.Provider value={value}><MemoryRouter><HomePage /><Location /></MemoryRouter></AuthContext.Provider>
  }
  return render(<Harness />)
}
async function submitLogin() {
  const user = userEvent.setup()
  const dialog = within(screen.getByRole('dialog'))
  await user.type(dialog.getByLabelText('用户名'), 'alice')
  await user.type(dialog.getByLabelText('密码'), 'password123')
  await user.click(dialog.getByRole('button', { name: '登录', exact: true }))
}

describe('HomePage', () => {
  it('allows guests to start querying without an account or navigation header', () => {
    mount()
    expect(screen.getByRole('link', { name: '开始查询' })).toHaveAttribute('href', '/explore')
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.getByAltText('福州海湾，远山、沙滩与礁石')).toBeInTheDocument()
  })
  it('starts registration in the correct mode and clears closed fields', async () => {
    mount(); const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: '注册', exact: true }))
    expect(screen.getByRole('button', { name: '注册并登录' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('用户名'), 'alice')
    await user.click(screen.getByRole('button', { name: '关闭' }))
    await user.click(screen.getByRole('button', { name: '登录', exact: true }))
    expect(screen.getByLabelText('用户名')).toHaveValue('')
    expect(within(screen.getByRole('dialog')).getByRole('tab', { name: '登录' })).toHaveAttribute('aria-selected', 'true')
  })
  it('keeps regular login on the homepage and replaces guest controls', async () => {
    mount(); await userEvent.setup().click(screen.getByRole('button', { name: '登录', exact: true }))
    await submitLogin()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByLabelText('路径')).toHaveTextContent(/^\/$/)
    expect(screen.getByRole('link', { name: '收藏' })).toHaveAttribute('href', '/favorites')
    expect(screen.getByRole('link', { name: '历史' })).toHaveAttribute('href', '/history')
    expect(screen.getByRole('link', { name: '我的计划' })).toHaveAttribute('href', '/plans')
    expect(screen.getByText('alice')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '注册', exact: true })).not.toBeInTheDocument()
  })
  it('continues to plans after login initiated from my plans', async () => {
    mount(); await userEvent.setup().click(screen.getByRole('button', { name: '我的计划' }))
    await submitLogin()
    await waitFor(() => expect(screen.getByLabelText('路径')).toHaveTextContent('/plans'))
  })
  it('cancels a protected intent without changing the homepage', async () => {
    mount(); const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: '我的计划' }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByLabelText('路径')).toHaveTextContent(/^\/$/)
    await user.click(screen.getByRole('button', { name: '登录', exact: true }))
    await submitLogin()
    expect(screen.getByLabelText('路径')).toHaveTextContent(/^\/$/)
  })
  it('reserves account space while initializing rather than flashing guest actions', () => {
    mount({ initializing: true })
    expect(within(screen.getByRole('main')).getByRole('status')).toHaveTextContent('正在确认登录状态')
    expect(screen.queryByRole('button', { name: '登录', exact: true })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '开始查询' })).toBeInTheDocument()
  })
  it('restores guest actions after a successful logout', async () => {
    mount({ user: { id: 'home-user', username: 'alice' } })
    await userEvent.setup().click(screen.getByRole('button', { name: '退出登录' }))
    expect(screen.getByRole('button', { name: '登录', exact: true })).toBeInTheDocument()
  })
  it('disables logout while pending and keeps the account on failure', async () => {
    let reject!: (reason: Error) => void
    const logout = vi.fn(() => new Promise<void>((_, fail) => { reject = fail }))
    mount({ user: { id: 'home-user', username: 'alice' }, logout })
    const button = screen.getByRole('button', { name: '退出登录' })
    await userEvent.setup().click(button)
    expect(button).toBeDisabled()
    reject(new Error('offline'))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('退出失败'))
    expect(screen.getByRole('link', { name: '收藏' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '退出登录' })).toBeEnabled()
  })
})
