import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { apiClient } from '../src/api/client'
import { AppShell } from '../src/app/AppShell'
import { AuthProvider } from '../src/features/auth/AuthProvider'

describe('AppShell', () => {
  it('renders the application navigation and child content', () => {
    vi.spyOn(apiClient, 'me').mockResolvedValue(null)
    render(
      <AuthProvider>
        <MemoryRouter>
          <AppShell>
            <p>Route content</p>
          </AppShell>
        </MemoryRouter>
      </AuthProvider>,
    )

    expect(screen.getByRole('link', { name: 'RoamBot' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '推荐' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '收藏' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '历史' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '账户' })).toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveTextContent('Route content')
  })
})
