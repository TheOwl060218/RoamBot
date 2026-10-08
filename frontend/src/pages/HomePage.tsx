import { ArrowRight, ArrowUpRight } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import photo from '../assets/fuzhou-home.jpg'
import { AuthDialog } from '../features/auth/AuthDialog'
import { useAuth } from '../features/auth/authContext'

export function HomePage() {
  const { user, initializing, logout } = useAuth()
  const navigate = useNavigate()
  const startRef = useRef<HTMLAnchorElement>(null)
  const logoutLock = useRef(false)
  const [dialog, setDialog] = useState<{ mode: 'login' | 'register'; target?: '/plans' } | null>(null)
  const [exiting, setExiting] = useState(false)
  const [error, setError] = useState('')

  async function exit() {
    if (logoutLock.current) return
    logoutLock.current = true
    setExiting(true)
    setError('')
    try {
      await logout()
      startRef.current?.focus()
    } catch {
      setError('退出失败，请稍后重试。')
    } finally {
      logoutLock.current = false
      setExiting(false)
    }
  }

  return (
    <>
      <main className="home-scene" aria-label="RoamBot 首页">
        <img className="home-photo" src={photo} alt="福州海湾，远山、沙滩与礁石" fetchPriority="high" />
        <div className="home-blur" aria-hidden="true" />
        <div className="home-shade" aria-hidden="true" />
        <div className="home-content">
          <div className="home-brand"><span className="home-logo" aria-hidden="true">R</span><h1>RoamBot</h1></div>
          <div className="home-actions">
            <Link className="home-start" ref={startRef} to="/recommend"><span>开始查询</span><ArrowRight aria-hidden="true" size={20} /></Link>
            {initializing ? (
              <div className="home-session-placeholder" aria-busy="true">
                <div className="home-first-row" role="status">正在确认登录状态…</div><div className="home-second-row" />
              </div>
            ) : user ? (
              <>
                <div className="home-shortcuts home-first-row" aria-label="个人功能">
                  <Link to="/favorites">收藏</Link><Link to="/history">历史</Link><Link to="/plans">我的计划</Link>
                </div>
                <div className="home-account-state home-second-row">
                  <span className="home-username" title={user.username}>{user.username}</span><span aria-hidden="true">·</span>
                  <button type="button" aria-label="退出登录" disabled={exiting} onClick={() => void exit()}>{exiting ? '退出中…' : '退出'}</button>
                </div>
              </>
            ) : (
              <>
                <div className="home-account home-first-row">
                  <button type="button" onClick={() => setDialog({ mode: 'login' })}>登录</button><span aria-hidden="true" />
                  <button type="button" onClick={() => setDialog({ mode: 'register' })}>注册</button>
                </div>
                <button type="button" className="home-plan home-second-row" onClick={() => setDialog({ mode: 'login', target: '/plans' })}>我的计划<ArrowUpRight aria-hidden="true" size={16} /></button>
              </>
            )}
            {error && <p className="home-error" role="alert">{error}</p>}
          </div>
        </div>
        <span className="home-location"><span>拍摄地：</span>福州</span>
      </main>
      {dialog && <AuthDialog open initialMode={dialog.mode} onClose={() => setDialog(null)} onAuthenticated={() => {
        const target = dialog.target
        setDialog(null)
        if (target) navigate(target)
        else startRef.current?.focus()
      }} />}
    </>
  )
}
