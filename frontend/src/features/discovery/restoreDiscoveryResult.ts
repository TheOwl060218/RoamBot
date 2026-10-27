import { apiClient, ApiError } from '../../api/client'
import type { HistorySummary } from '../../api/types'
import type { DiscoverySnapshot } from './types'

export type SavedDiscoveryResult = { id: string; history_id?: string | null; message: string }
const guestKey = 'roambot.discovery-result.v2:guest'
export function readSavedDiscovery(key: string, signedIn: boolean): SavedDiscoveryResult | null {
  const read = (store: Storage, name: string) => {
    try {
      const value = JSON.parse(store.getItem(name) ?? 'null')
      if (value?.expires != null && value.expires <= Date.now()) { store.removeItem(name); return null }
      return typeof value?.id === 'string' && typeof value?.message === 'string' ? value as SavedDiscoveryResult : null
    } catch { return null }
  }
  return read(sessionStorage, key) ?? (signedIn ? null : read(localStorage, guestKey))
}
export function saveDiscoveryReference(key: string, value: SavedDiscoveryResult, signedIn: boolean) {
  try { sessionStorage.setItem(key, JSON.stringify({ ...value, expires: Date.now()+86400000 })) } catch { /* The other store can still be usable. */ }
  try {
    if (signedIn) { localStorage.removeItem(guestKey); sessionStorage.removeItem('roambot.discovery-result.v1:guest'); return }
    const previous = JSON.parse(localStorage.getItem(guestKey) ?? 'null')
    localStorage.setItem(guestKey, JSON.stringify({ ...value, expires: previous?.id === value.id ? previous.expires : Date.now()+86400000 }))
  } catch { /* A blocked persistent store still permits the current tab to work. */ }
}

/** Rebind server-owned results; never recreate recommendations from browser data. */
export async function restoreDiscoveryResult(saved: SavedDiscoveryResult | null, signedIn: boolean) {
  const missing = (error: unknown) => error instanceof ApiError && error.status === 404
  const result = (snapshot: DiscoverySnapshot, message?: string) => ({ snapshot,
    message: snapshot.search_request || message || snapshot.conversation?.filter(turn => turn.role === 'user').at(-1)?.content || '' })
  if (saved) {
    try { return result(await apiClient.get<DiscoverySnapshot>(`/discovery/jobs/${encodeURIComponent(saved.id)}`), saved.message) }
    catch (error) { if (!missing(error)) throw error }
    if (signedIn && saved.history_id) {
      try { return result(await apiClient.post<DiscoverySnapshot>(`/discovery/history/${encodeURIComponent(saved.history_id)}/restore`), saved.message) }
      catch (error) { if (!missing(error)) throw error }
    }
  }
  if (!signedIn) return null
  const { histories } = await apiClient.get<{ histories: HistorySummary[] }>('/history')
  const latest = histories.filter(history => history.mode === 'discovery' && history.item_count > 0)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
  if (!latest) return null
  return result(await apiClient.post<DiscoverySnapshot>(`/discovery/history/${encodeURIComponent(latest.id)}/restore`))
}
