import { useEffect, useState, type PropsWithChildren } from 'react'
import { UserRound } from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'

import { AuthDialog } from '../features/auth/AuthDialog'
import { useAuth } from '../features/auth/authContext'
import { ACCOUNT_DIALOG_REQUEST_EVENT } from './accountDialog'
import { HOME_RESET_REQUEST_EVENT, clearSearchResult } from '../features/search/formState'
import { PlanNavigation } from '../features/plans/PlanNavigation'

const navigation = [
  { label: '推荐', to: '/recommend' },
  { label: '收藏', to: '/favorites' },
  { label: '历史', to: '/history' },
]

export function AppShell({ children }: PropsWithChildren) {
  const [accountOpen, setAccountOpen] = useState(false)
  const [accountTarget, setAccountTarget] = useState<'/plans' | null>(null)
  const [status, setStatus] = useState('')
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (!status) return
    const timer = window.setTimeout(() => setStatus(''), 2400)
    return () => window.clearTimeout(timer)
  }, [status])

  useEffect(() => {
    const openAccount = (event: Event) => {
      const target = (event as CustomEvent<{ target?: string }>).detail?.target
      setAccountTarget(target === '/plans' ? '/plans' : null)
      setAccountOpen(true)
    }
    window.addEventListener(ACCOUNT_DIALOG_REQUEST_EVENT, openAccount)
    return () => window.removeEventListener(ACCOUNT_DIALOG_REQUEST_EVENT, openAccount)
  }, [])

  function goRecommend() {
    clearSearchResult()
    if (location.pathname !== '/recommend') {
      navigate('/recommend')
    }
    window.dispatchEvent(new Event(HOME_RESET_REQUEST_EVENT))
  }

  return (
    <div className="app-shell">
      <header className="shell-header">
        <div className="brand-navigation">
          <NavLink className="brand" to="/" aria-label="RoamBot">
            <span aria-hidden="true" className="brand-mark">R</span>
            <span>RoamBot</span>
          </NavLink>
          <NavLink className="shell-home-link" to="/" end>首页</NavLink>
        </div>

        <div className='mobile-plan-status'><PlanNavigation mobile /></div>

        <nav className="primary-nav" aria-label="主导航">
          <PlanNavigation />
          {navigation.map((item) => (
            <NavLink
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              end={item.to === '/recommend'}
              key={item.label}
              to={item.to}
              onClick={item.to === '/recommend' ? goRecommend : undefined}
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
          onClick={() => { setAccountTarget(null); setAccountOpen(true) }}
        >
          {user ? <span className="account-initial">{user.username.slice(0, 1).toUpperCase()}</span> : (
            <UserRound aria-hidden="true" size={20} strokeWidth={1.8} />
          )}
        </button>
      </header>

      <main className="shell-main">{children}</main>
      {status && <div className="app-toast" role="status">{status}</div>}
      <AuthDialog open={accountOpen} onClose={() => { setAccountOpen(false); setAccountTarget(null) }} onStatus={setStatus} onAuthenticated={() => {
        setAccountOpen(false)
        if (accountTarget) navigate(accountTarget)
        setAccountTarget(null)
      }} />
    </div>
  )
}
