import { useEffect, useMemo, useState, type PropsWithChildren } from 'react'

import { apiClient } from '../../api/client'
import type { AuthResponse } from '../../api/types'
import { AuthContext, type AuthContextValue } from './authContext'

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<AuthResponse | null>(apiClient.authSession)
  const [initializing, setInitializing] = useState(true)

  useEffect(() => {
    const unsubscribe = apiClient.subscribe(setSession)
    void apiClient.me().catch(() => null).finally(() => setInitializing(false))
    return unsubscribe
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      initializing,
      login: async (username, password) => {
        await apiClient.login(username, password)
      },
      register: async (username, password) => {
        await apiClient.register(username, password)
      },
      logout: async () => {
        await apiClient.logout()
      },
    }),
    [initializing, session],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
