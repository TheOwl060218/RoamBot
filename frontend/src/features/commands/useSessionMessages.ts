import { useCallback, useEffect, useState, type SetStateAction } from 'react'

type Message = { role: string; content: string; id?: string }
const keyFor = (scope: string, owner: string | null) => `roambot.chat.v1:${encodeURIComponent(scope)}:${owner === null ? 'guest' : 'user:' + encodeURIComponent(owner)}`
function read<T extends Message>(key: string, fallback: T[]): T[] {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(key) ?? 'null')
    if (Array.isArray(value) && value.every(item => item && ['user', 'assistant'].includes(item.role) && typeof item.content === 'string' && (item.id === undefined || typeof item.id === 'string'))) return value as T[]
  } catch { /* Storage may be disabled; the live conversation remains usable. */ }
  return fallback
}

/** Only visible dialogue, scoped to this tab/account. No credentials or execution state. */
export function useSessionMessages<T extends Message>(scope: string, owner: string | null, ready: boolean, initial: T[] = []) {
  const key = keyFor(scope, owner), guestKey = keyFor(scope, null)
  const [state, setState] = useState(() => ({ key: ready ? key : null, scope, items: ready ? read(key, initial) : [] as T[], adopted: false }))
  const [unavailable, setUnavailable] = useState(false)
  if (ready && state.key !== key) {
    const adoptGuest = state.scope === scope && state.key === guestKey && owner !== null && state.items.length > 0
    const seed = state.key === null || state.scope !== scope ? initial : []
    setState({ key, scope, items: adoptGuest ? state.items : read(key, seed), adopted: adoptGuest })
  }
  useEffect(() => {
    if (!ready || state.key !== key) return
    let active = true
    let failed = false
    try {
      sessionStorage.setItem(key, JSON.stringify(state.items))
      if (state.adopted) sessionStorage.removeItem(guestKey)
    } catch { failed = true }
    queueMicrotask(() => { if (active) setUnavailable(failed) })
    return () => { active = false }
  }, [state, key, guestKey, ready])
  const update = useCallback((value: SetStateAction<T[]>) => {
    setState(current => current.key !== key ? current : { ...current,
      items: typeof value === 'function' ? value(current.items) : value })
  }, [key])
  return [ready && state.key === key ? state.items : [], update, unavailable] as const
}
