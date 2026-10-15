import { CircleHelp, Eye, EyeOff, LogOut, X } from 'lucide-react'
import { useEffect, useId, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { createPortal } from 'react-dom'

import { ApiError } from '../../api/client'
import { useAuth } from './authContext'
import { useLayerExit } from '../studio/useLayerExit'
import { useModalLayer } from '../studio/useModalLayer'

type AuthDialogProps = {
  open: boolean
  onClose: () => void
  onAuthenticated?: () => void
  onStatus?: (message: string) => void
  initialMode?: 'login' | 'register'
}

export function AuthDialog(props: AuthDialogProps) {
  return props.open ? createPortal(<AuthDialogContent {...props} />, document.body) : null
}

function AuthDialogContent({ open, onClose, onAuthenticated, onStatus, initialMode = 'login' }: AuthDialogProps) {
  const layer = useRef<HTMLDialogElement>(null)
  const previousFocus = useRef(document.activeElement as HTMLElement | null)
  useLayerExit(layer, '.auth-dialog')
  useModalLayer(layer)
  // A body Portal escapes CSS stacking contexts; showModal also puts account
  // UI above an existing native plan dialog and browser view-transition layer.
  useLayoutEffect(() => {
    const element = layer.current
    if (element && !element.open) {
      if (typeof element.showModal === 'function') element.showModal()
      else element.setAttribute('open', '')
    }
  }, [])
  const { user, login, register, logout } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>(initialMode)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const dialogRef = useRef<HTMLElement>(null)
  const passwordId = useId()
  const outsideDown = useRef(false)

  useEffect(() => {
    if (!open) return
    const trigger = previousFocus.current
    const dialog = dialogRef.current
    const first = dialog?.querySelector<HTMLElement>('input, button, [href], [tabindex]:not([tabindex="-1"])')
    first?.focus({ preventScroll: true })
    return () => trigger?.focus({ preventScroll: true })
  }, [open])

  if (!open) return null

  function resetForm() {
    setMode('login')
    setUsername('')
    setPassword('')
    setError('')
    setShowPassword(false)
  }

  function closeDialog() {
    resetForm()
    onClose()
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (mode === 'login') {
      if (!/^[A-Za-z0-9_]{3,32}$/.test(username) || password.length < 8 || password.length > 128) {
        setError('用户名或密码不正确。')
        return
      }
    } else {
      if (!/^[A-Za-z0-9_]{3,32}$/.test(username)) {
        setError('用户名需为 3–32 位字母、数字或下划线。')
        return
      }
      if (password.length < 8 || password.length > 128) {
        setError('注册密码需为 8–128 位字符。')
        return
      }
    }
    setSubmitting(true)
    try {
      if (mode === 'login') await login(username, password)
      else await register(username, password)
      onStatus?.(mode === 'login' ? '登录成功。' : '账户创建成功，已登录。')
      resetForm()
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
      closeDialog()
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
    <dialog ref={layer} className="dialog-backdrop auth-layer" role="presentation" onCancel={event => { event.preventDefault(); closeDialog() }} onPointerDown={event => { outsideDown.current = event.target === event.currentTarget }} onPointerUp={event => { if (outsideDown.current && event.target === event.currentTarget) closeDialog(); outsideDown.current = false }}>
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
          <button className="icon-button" type="button" aria-label="关闭" onClick={closeDialog}>
            <X aria-hidden="true" size={19} />
          </button>
        </header>

        {user ? (
          <div className="account-panel">
            <button
              className="icon-text-button"
              type="button"
              onClick={async () => {
                await logout()
                onStatus?.('已退出登录。')
                closeDialog()
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
              <div className="field">
                <span className="password-label">
                  <label htmlFor={passwordId}>密码</label>
                  {mode === 'login' && (
                    <button
                      className="password-help"
                      type="button"
                      aria-label="查看密码要求"
                      title="注册密码需为 8–128 位字符。"
                    >
                      <CircleHelp aria-hidden="true" size={15} />
                    </button>
                  )}
                </span>
                <span className="password-field">
                  <input
                    id={passwordId}
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
              </div>
              <div className="auth-message-slot">
                {error && <div className="field-error" role="alert">{error}</div>}
              </div>
              <button className="primary-button" type="submit" disabled={submitting}>
                {submitting ? '请稍候…' : mode === 'login' ? '登录' : '注册并登录'}
              </button>
            </form>
          </>
        )}
      </section>
    </dialog>
  )
}
