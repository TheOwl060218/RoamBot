import { useState, type PropsWithChildren } from 'react'
import { UserRound } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { AuthDialog } from '../features/auth/AuthDialog'
import { useAuth } from '../features/auth/authContext'

const navigation = [
  { label: '推荐', to: '/' },
  { label: '收藏', to: '/favorites' },
  { label: '历史', to: '/history' },
]

export function AppShell({ children }: PropsWithChildren) {
  const [accountOpen, setAccountOpen] = useState(false)
  const { user } = useAuth()
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

        <button
          className="account-button"
          type="button"
          aria-label="账户"
          title={user ? `账户：${user.username}` : '登录或创建账户'}
          onClick={() => setAccountOpen(true)}
        >
          {user ? <span className="account-initial">{user.username.slice(0, 1).toUpperCase()}</span> : (
            <UserRound aria-hidden="true" size={20} strokeWidth={1.8} />
          )}
        </button>
      </header>

      <main className="shell-main">{children}</main>
      <AuthDialog open={accountOpen} onClose={() => setAccountOpen(false)} />
    </div>
  )
}
