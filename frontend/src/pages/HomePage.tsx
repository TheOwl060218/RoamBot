import { ArrowRight } from 'lucide-react'
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
        <div className="home-shade" aria-hidden="true" />
        <header className='home-header'>
          <div className='home-account-bar' aria-label='账户功能'>
            {initializing ? <span className='home-session-placeholder' role='status'>正在确认登录状态…</span> : user ? <>
              <Link to='/favorites' viewTransition>收藏</Link><Link to='/history' viewTransition>历史</Link>
              <div className='home-account-state'><span className='home-username' title={user.username}>{user.username}</span>
                <button type='button' aria-label='退出登录' disabled={exiting} onClick={() => void exit()}>{exiting ? '退出中…' : '退出'}</button>
              </div>
            </> : <div className='home-guest-account'>
              <button type='button' onClick={() => setDialog({ mode: 'login' })}>登录</button>
              <button type='button' onClick={() => setDialog({ mode: 'register' })}>注册</button>
            </div>}
          </div>
          {error && <p className='home-error' role='alert'>{error}</p>}
        </header>
        <div className="home-content">
          <div className="home-brand"><span className="home-logo" aria-hidden="true">R</span><h1>RoamBot</h1></div>
          <div className="home-actions">
            <Link className="home-start" ref={startRef} to="/explore" state={{ homeEntry: true }} viewTransition><span>开始探索</span><ArrowRight aria-hidden="true" size={20} /></Link>
            <div className='home-shortcuts' aria-label='出行功能'>
              <Link to='/itineraries' viewTransition>行程中心</Link>
              {user ? <Link to='/plans' viewTransition>同行计划</Link> : <button type='button' className='home-plan' onClick={() => setDialog({ mode: 'login', target: '/plans' })}>同行计划</button>}
            </div>
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
