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
    expect(screen.getByRole('link', { name: '推荐' })).toHaveAttribute('href', '/explore')
    expect(screen.getByRole('link', { name: '收藏' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '历史' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '账户' })).toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveTextContent('Route content')
  })

  it('places an explicit home link beside the brand', () => {
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

    const home = screen.getByRole('link', { name: '首页', exact: true })
    expect(home).toHaveAttribute('href', '/')
    expect(home.parentElement).toBe(screen.getByRole('link', { name: 'RoamBot' }).parentElement)
    expect(screen.getByRole('link', { name: '推荐' })).toBeInTheDocument()
  })

  it('owns one shared coastal backdrop behind the route content', () => {
    vi.spyOn(apiClient, 'me').mockResolvedValue(null)
    const { rerender } = render(
      <AuthProvider>
        <MemoryRouter>
          <AppShell><p>推荐内容</p></AppShell>
        </MemoryRouter>
      </AuthProvider>,
    )

    const backdrop = screen.getByTestId('coastal-backdrop')
    expect(backdrop).toHaveAttribute('aria-hidden', 'true')
    expect(document.querySelector('.app-shell')).toHaveClass('coastal-shell')

    rerender(
      <AuthProvider>
        <MemoryRouter>
          <AppShell><p>收藏内容</p></AppShell>
        </MemoryRouter>
      </AuthProvider>,
    )
    expect(screen.getByTestId('coastal-backdrop')).toBe(backdrop)
  })
})
