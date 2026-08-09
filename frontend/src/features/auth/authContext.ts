import { createContext, useContext } from 'react'

import type { AuthResponse } from '../../api/types'

export type AuthContextValue = {
  user: AuthResponse['user'] | null
  initializing: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
