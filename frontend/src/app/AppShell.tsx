import { useEffect, useRef, useState, type PropsWithChildren } from 'react'
import { UserRound } from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'

import { AuthDialog } from '../features/auth/AuthDialog'
import { useAuth } from '../features/auth/authContext'
import { ACCOUNT_DIALOG_REQUEST_EVENT } from './accountDialog'
import { PlanNavigation } from '../features/plans/PlanNavigation'
import { CoastalBackdrop } from './CoastalBackdrop'
import { RouteTransitionFrame } from './RouteTransitionFrame'
import { useBusinessAssistant, useCommandTarget } from '../features/commands/commandContext'

const navigation = [
  { label: '行程中心', to: '/itineraries' },
  { label: '推荐', to: '/explore' },
  { label: '收藏', to: '/favorites' },
  { label: '历史', to: '/history' },
]

export function AppShell({ children }: PropsWithChildren) {
  const [accountOpen, setAccountOpen] = useState(false)
  const [accountMode, setAccountMode] = useState<'login' | 'register'>('login')
  const [accountTarget, setAccountTarget] = useState<'/plans' | null>(null)
  const [status, setStatus] = useState('')
  const main = useRef<HTMLElement>(null)
  const { user } = useAuth()
  const navigate = useNavigate()
  const assistant = useBusinessAssistant()
  const { pathname } = useLocation()
  useCommandTarget('shell', () => ({}), effect => {
    if (effect.tool !== 'open_account') return false
    setAccountMode(effect.arguments.mode === 'register' ? 'register' : 'login')
    setAccountTarget(null); setAccountOpen(true)
    return true
  })

  useEffect(() => {
    const onScroll = () => {
      const content = main.current
      const header = document.querySelector<HTMLElement>('.shell-header')
      if (!content || !header) return
      content.style.setProperty('--shell-header-height', `${header.offsetHeight}px`)
      const browse = content.querySelector<HTMLElement>('.discovery-browse')
      browse?.classList.toggle('is-scrolled', browse.scrollTop > 8)
      header.classList.toggle('is-scrolled', window.scrollY > 8 || (browse?.scrollTop ?? 0) > 8)
    }
    const resize = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(onScroll)
    if (main.current) resize?.observe(main.current)
    const header = document.querySelector<HTMLElement>('.shell-header')
    if (header) resize?.observe(header)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    const scrollRegion = main.current
    scrollRegion?.addEventListener('scroll', onScroll, { capture: true, passive: true })
    window.addEventListener('resize', onScroll)
    return () => { resize?.disconnect(); scrollRegion?.removeEventListener('scroll', onScroll, true); window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll) }
  }, [])

  useEffect(() => {
    if (!status) return
    const timer = window.setTimeout(() => setStatus(''), 2400)
    return () => window.clearTimeout(timer)
  }, [status])

  useEffect(() => {
    const openAccount = (event: Event) => {
      const { target, mode } = (event as CustomEvent<{ target?: string; mode?: string }>).detail ?? {}
      setAccountMode(mode === 'register' ? 'register' : 'login')
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
              key={item.label}
              to={item.to}
              viewTransition
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className='shell-account-actions'>
        {!['/explore', '/recommend'].includes(pathname) && <div ref={assistant?.setChatAnchor} className='shell-assistant-anchor' />}
        <button
          className="account-button"
          type="button"
          aria-label="账户"
          title={user ? `账户：${user.username}` : '登录或创建账户'}
          onClick={() => { setAccountTarget(null); setAccountMode('login'); setAccountOpen(true) }}
        >
          {user ? <span className="account-initial">{user.username.slice(0, 1).toUpperCase()}</span> : (
            <UserRound aria-hidden="true" size={20} strokeWidth={1.8} />
          )}
        </button>
        </div>
      </header>

      <main ref={main} className="shell-main"><RouteTransitionFrame>{children}</RouteTransitionFrame></main>
      {status && <div className="app-toast" role="status">{status}</div>}
      <AuthDialog open={accountOpen} initialMode={accountMode} onClose={() => { setAccountOpen(false); setAccountTarget(null) }} onStatus={setStatus} onAuthenticated={() => {
        setAccountOpen(false)
        if (accountTarget) navigate(accountTarget)
        setAccountTarget(null)
      }} />
    </div>
  )
}
