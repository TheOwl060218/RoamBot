import { useEffect, useRef, useState, type PropsWithChildren } from 'react'
import { UserRound } from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'

import { AuthDialog } from '../features/auth/AuthDialog'
import { useAuth } from '../features/auth/authContext'
import { ACCOUNT_DIALOG_REQUEST_EVENT } from './accountDialog'
import { PlanNavigation } from '../features/plans/PlanNavigation'
import { CoastalBackdrop } from './CoastalBackdrop'
import { RouteTransitionFrame } from './RouteTransitionFrame'

const navigation = [
  { label: '推荐', to: '/recommend' },
  { label: '收藏', to: '/favorites' },
  { label: '历史', to: '/history' },
]

export function AppShell({ children }: PropsWithChildren) {
  const [accountOpen, setAccountOpen] = useState(false)
  const [accountTarget, setAccountTarget] = useState<'/plans' | null>(null)
  const [status, setStatus] = useState('')
  const main = useRef<HTMLElement>(null)
  const { user } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    const onScroll = () => {
      const content = main.current
      const header = document.querySelector<HTMLElement>('.shell-header')
      if (!content || !header) return
      const overlap = header.getBoundingClientRect().bottom - content.getBoundingClientRect().top
      content.style.setProperty('--shell-fade-end', `${Math.max(0, overlap) + 72}px`)
      content.style.setProperty('--shell-fade-start', `${Math.max(0, overlap)}px`)
      content.classList.toggle('is-scrolled', window.scrollY > 8)
    }
    const resize = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(onScroll)
    if (main.current) resize?.observe(main.current)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => { resize?.disconnect(); window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll) }
  }, [])

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

  return (
    <div className="app-shell coastal-shell">
      <CoastalBackdrop />
      <header className='shell-header'>
        <div className="brand-navigation">
          <NavLink className="brand" to="/" aria-label="RoamBot" viewTransition>
            <span aria-hidden="true" className="brand-mark">R</span>
            <span>RoamBot</span>
          </NavLink>
          <NavLink className="shell-home-link" to="/" end viewTransition>首页</NavLink>
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
              viewTransition
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

      <main ref={main} className="shell-main"><RouteTransitionFrame>{children}</RouteTransitionFrame></main>
      {status && <div className="app-toast" role="status">{status}</div>}
      <AuthDialog open={accountOpen} onClose={() => { setAccountOpen(false); setAccountTarget(null) }} onStatus={setStatus} onAuthenticated={() => {
        setAccountOpen(false)
        if (accountTarget) navigate(accountTarget)
        setAccountTarget(null)
      }} />
    </div>
  )
}
