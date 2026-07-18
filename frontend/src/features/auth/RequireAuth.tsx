import type { PropsWithChildren } from 'react'
import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

import { AuthDialog } from './AuthDialog'
import { useAuth } from './authContext'

export function RequireAuth({ children }: PropsWithChildren) {
  const { user, initializing } = useAuth()
  const navigate = useNavigate()
  const cancel = useCallback(() => navigate('/'), [navigate])
  if (initializing) return <p className="loading-state">正在确认登录状态…</p>
  if (!user) return <AuthDialog open onClose={cancel} onAuthenticated={() => undefined} />
  return children
}
