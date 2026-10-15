import type { PropsWithChildren } from 'react'
import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'

import { AuthDialog } from './AuthDialog'
import { useAuth } from './authContext'

export function RequireAuth({ children }: PropsWithChildren) {
  const { user, initializing } = useAuth()
  const navigate = useNavigate()
  const [askLogin, setAskLogin] = useState(false)
  if (initializing) return <p className="loading-state">正在确认登录状态…</p>
  if (!user) {
    return (
      <div className="auth-required-hint">
        <p>登录后可查看此页面。</p>
        <div className="auth-required-actions">
          <button className="text-button" type="button" onClick={() => setAskLogin(true)}>去登录</button>
          <button className="text-button" type="button" onClick={() => navigate('/')}>返回首页</button>
        </div>
        {askLogin && createPortal(<AuthDialog open onClose={() => setAskLogin(false)} onAuthenticated={() => setAskLogin(false)} />, document.body)}
      </div>
    )
  }
  return children
}
