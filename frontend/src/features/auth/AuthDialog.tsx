import { Eye, EyeOff, LogOut, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent } from 'react'

import { ApiError } from '../../api/client'
import { useAuth } from './authContext'

type AuthDialogProps = {
  open: boolean
  onClose: () => void
  onAuthenticated?: () => void
}

export function AuthDialog({ open, onClose, onAuthenticated }: AuthDialogProps) {
  const { user, login, register, logout } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const dialogRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!open) return
    const previousFocus = document.activeElement as HTMLElement | null
    const dialog = dialogRef.current
    const first = dialog?.querySelector<HTMLElement>('input, button, [href], [tabindex]:not([tabindex="-1"])')
    first?.focus()
    return () => previousFocus?.focus()
  }, [open])

  if (!open) return null

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (!/^[A-Za-z0-9_]{3,32}$/.test(username)) {
      setError('用户名需为 3–32 位字母、数字或下划线。')
      return
    }
    if (password.length < 8 || password.length > 128) {
      setError('密码长度需为 8–128 位。')
      return
    }
    setSubmitting(true)
    try {
      if (mode === 'login') await login(username, password)
      else await register(username, password)
      if (onAuthenticated) onAuthenticated()
      else onClose()
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === 'username_taken') {
        setError('这个用户名已被使用。')
      } else if (caught instanceof ApiError && caught.code === 'invalid_credentials') {
        setError('用户名或密码不正确。')
      } else {
        setError('账户请求失败，请稍后再试。')
      }
    } finally {
      setSubmitting(false)
    }
  }

  function trapFocus(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape') {
      event.preventDefault()
      onClose()
      return
    }
    if (event.key !== 'Tab') return
    const focusable = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>(
        'input:not([disabled]), button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      ),
    )
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation">
      <section
        className="auth-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={user ? '账户' : '登录 RoamBot'}
        ref={dialogRef}
        onKeyDown={trapFocus}
      >
        <header>
          <div>
            <p className="eyebrow">RoamBot 账户</p>
            <h2>{user ? user.username : mode === 'login' ? '登录 RoamBot' : '创建账户'}</h2>
          </div>
          <button className="icon-button" type="button" aria-label="关闭" onClick={onClose}>
            <X aria-hidden="true" size={19} />
          </button>
        </header>

        {user ? (
          <div className="account-panel">
            <p>登录后，成功查询会自动保存在历史中，并可收藏地点或创建分享。</p>
            <button
              className="icon-text-button"
              type="button"
              onClick={async () => {
                await logout()
                onClose()
              }}
            >
              <LogOut aria-hidden="true" size={17} />退出登录
            </button>
          </div>
        ) : (
          <>
            <div className="auth-tabs" role="tablist" aria-label="账户操作">
              <button role="tab" aria-selected={mode === 'login'} onClick={() => setMode('login')}>登录</button>
              <button role="tab" aria-selected={mode === 'register'} onClick={() => setMode('register')}>创建账户</button>
            </div>
            <form className="auth-form" onSubmit={submit}>
              <label className="field">
                <span>用户名</span>
                <input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} />
              </label>
              <label className="field">
                <span>密码</span>
                <span className="password-field">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                  <button
                    className="password-toggle"
                    type="button"
                    aria-label={showPassword ? '隐藏密码' : '显示密码'}
                    onClick={() => setShowPassword((visible) => !visible)}
                  >
                    {showPassword ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}
                  </button>
                </span>
              </label>
              {error && <div className="field-error" role="alert">{error}</div>}
              <button className="primary-button" type="submit" disabled={submitting}>
                {submitting ? '请稍候…' : mode === 'login' ? '登录' : '注册并登录'}
              </button>
            </form>
          </>
        )}
      </section>
    </div>
  )
}
