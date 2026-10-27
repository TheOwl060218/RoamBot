import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useMemo, useState } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { AuthResponse } from '../src/api/types'
import { AuthContext, type AuthContextValue } from '../src/features/auth/authContext'
import { RequireAuth } from '../src/features/auth/RequireAuth'

function ProtectedHarness() {
  const [user, setUser] = useState<AuthResponse['user'] | null>(null)
  const value = useMemo<AuthContextValue>(() => ({
    user,
    initializing: false,
    login: async () => setUser({ username: 'traveler' }),
    register: async () => setUser({ username: 'traveler' }),
    logout: vi.fn(),
  }), [user])

  return (
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={['/favorites']}>
        <Routes>
          <Route path="/" element={<p>Core page</p>} />
          <Route path="/favorites" element={<RequireAuth><p>Favorite content</p></RequireAuth>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>
  )
}

describe('RequireAuth', () => {
  it('shows a centered hint, then opens login on demand and reveals the page after success', async () => {
    const user = userEvent.setup()
    render(<ProtectedHarness />)

    expect(screen.queryByRole('dialog', { name: '登录 RoamBot' })).toBeNull()
    expect(screen.getByText('登录后可查看此页面。')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '去登录' }))

    expect(screen.getByRole('dialog', { name: '登录 RoamBot' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('用户名'), 'traveler')
    await user.type(screen.getByLabelText('密码'), 'password123')
    await user.click(screen.getByRole('button', { name: '登录' }))

    expect(await screen.findByText('Favorite content')).toBeInTheDocument()
  })

  it('renders the on-demand login dialog outside the page tree so portaled layers stay under it', async () => {
    const user = userEvent.setup()
    render(<ProtectedHarness />)

    await user.click(screen.getByRole('button', { name: '去登录' }))
    const backdrop = document.querySelector('.dialog-backdrop')!

    expect(backdrop.parentElement).toBe(document.body)
    expect(backdrop.closest('.auth-required-hint')).toBeNull()
  })
})
