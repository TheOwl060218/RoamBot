import type { PropsWithChildren } from 'react'
import { UserRound } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const navigation = [
  { label: '推荐', to: '/' },
  { label: '收藏', to: '/favorites' },
  { label: '历史', to: '/history' },
]

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="app-shell">
      <header className="shell-header">
        <NavLink className="brand" to="/" aria-label="RoamBot">
          <span aria-hidden="true" className="brand-mark">R</span>
          <span>RoamBot</span>
        </NavLink>

        <nav className="primary-nav" aria-label="主导航">
          {navigation.map((item) => (
            <NavLink
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              end={item.to === '/'}
              key={item.label}
              to={item.to}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <button className="account-button" type="button" aria-label="账户" title="账户">
          <UserRound aria-hidden="true" size={20} strokeWidth={1.8} />
        </button>
      </header>

      <main className="shell-main">{children}</main>
    </div>
  )
}
