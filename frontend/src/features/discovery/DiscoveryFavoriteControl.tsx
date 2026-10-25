import { useEffect, useRef, useState } from 'react'
import { apiClient } from '../../api/client'
import type { Favorite } from '../../api/types'
import { useAuth } from '../auth/authContext'
import { AuthDialog } from '../auth/AuthDialog'
import type { DiscoveryCard } from './types'
import { Star } from 'lucide-react'
import { BUSINESS_CHANGED } from '../commands/commandEvents'

let inFlight: { username: string; request: Promise<{ favorites: Favorite[] }> } | null = null
function loadFavorites(username: string) {
  if (inFlight?.username === username) return inFlight.request
  const request = apiClient.get<{ favorites: Favorite[] }>('/favorites')
  inFlight = { username, request }
  void request.finally(() => { if (inFlight?.request === request) inFlight = null }).catch(() => undefined)
  return request
}
const changedEvent = 'roambot:discovery-favorite-changed'
type FavoriteChange = { username: string; provider: string; placeId: string; savedId: string | null }

export function DiscoveryFavoriteControl({ card, source, compact = false }: { card: DiscoveryCard; source: 'live' | 'demo'; compact?: boolean }) {
  const { user } = useAuth()
  const [saved, setSaved] = useState<string | null>(null), [busy, setBusy] = useState(false)
  const [auth, setAuth] = useState(false), [error, setError] = useState('')
  const lock = useRef(false), revision = useRef(0)
  const provider = source === 'demo' ? 'mock' : 'amap', id = card.place.id.split(':').at(-1)!
  useEffect(() => {
    if (!user) return
    ++revision.current
    let active = true
    const changed = (event: Event) => {
      const detail = (event as CustomEvent<FavoriteChange>).detail
      if (detail.username === user.username && detail.provider === provider && detail.placeId === id) {
        revision.current++; setSaved(detail.savedId)
      }
    }
    window.addEventListener(changedEvent, changed)
    const refresh = () => {
      const version = ++revision.current
      void loadFavorites(user.username).then(result => {
        if (active && version === revision.current) setSaved(result.favorites.find(f => f.place.provider === provider && f.place.provider_place_id === id)?.id ?? null)
      }).catch(() => undefined)
    }
    window.addEventListener(BUSINESS_CHANGED, refresh)
    refresh()
    return () => { active = false; window.removeEventListener(changedEvent, changed); window.removeEventListener(BUSINESS_CHANGED, refresh) }
  }, [user, id, provider])
  async function toggle() {
    if (lock.current) return
    lock.current = true; revision.current++; setBusy(true); setError('')
    try {
      let savedId: string | null = null
      if (saved) { await apiClient.delete(`/favorites/${saved}`); setSaved(null) }
      else {
        const p = card.place
        const result = await apiClient.post<{ favorite: Favorite }>('/favorites', { provider, destination: {
          provider_id: id, name: p.name, city: p.city, address: p.address, coordinate: p.coordinate, type_name: p.map_type, type_code: '',
        } })
        savedId = result.favorite.id; setSaved(savedId)
      }
      const username = apiClient.authSession?.user.username ?? user?.username
      if (username) window.dispatchEvent(new CustomEvent<FavoriteChange>(changedEvent,
        { detail: { username, provider, placeId: id, savedId } }))
    } catch (caught) { setError(caught instanceof Error ? caught.message : '收藏未完成。') }
    finally { lock.current = false; setBusy(false) }
  }
  const label = busy ? '正在保存…' : saved ? '已收藏' : '收藏地点'
  return <><button type='button' className={compact ? 'discovery-card-favorite' : 'text-button'} disabled={busy} aria-pressed={!!saved}
    aria-label={compact ? `${saved ? '取消收藏' : '收藏'}${card.place.name}` : undefined} title={label}
    onPointerDown={compact ? event => event.stopPropagation() : undefined}
    onClick={() => { if (!user) setAuth(true); else void toggle() }}>{compact ? <Star size={17} fill={saved ? 'currentColor' : 'none'} aria-hidden='true' /> : label}</button>
    {error && <p className={compact ? 'discovery-card-favorite-error' : undefined} role='alert'>{error}</p>}
    <AuthDialog open={auth} onClose={() => setAuth(false)} onAuthenticated={() => { setAuth(false); void toggle() }} />
  </>
}
