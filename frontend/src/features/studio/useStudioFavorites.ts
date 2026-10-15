import { useEffect, useRef, useState } from 'react'
import { apiClient } from '../../api/client'
import type { Favorite, RecommendationItem, SourceState } from '../../api/types'
import { requestAccountDialog } from '../../app/accountDialog'
export function useStudioFavorites(username: string | null, source?: SourceState) {
  const [favorites, setFavorites] = useState<Record<string, Favorite>>({})
  const [pending, setPending] = useState<string[]>([])
  const [notice, setNotice] = useState('')
  const current = useRef(username), locks = useRef(new Set<string>())
  useEffect(() => {
    current.current = username
    let alive = true
    void (username ? apiClient.get<{ favorites: Favorite[] }>('/favorites') : Promise.resolve({ favorites: [] })).then(r => {
      if (alive) setFavorites(Object.fromEntries(r.favorites.map(f => [f.place.provider_place_id, f])))
    }).catch(() => { if (alive) setFavorites({}) })
    return () => { alive = false }
  }, [username])
  async function toggle(item: RecommendationItem) {
    if (!username) { requestAccountDialog(); return }
    const id = item.destination.provider_id, owner = username
    if (locks.current.has(id)) return
    locks.current.add(id); setPending(p => [...p, id])
    try {
      const existing = favorites[id]
      if (existing) {
        await apiClient.delete(`/favorites/${existing.id}`)
        if (current.current === owner) setFavorites(v => { const next = { ...v }; delete next[id]; return next })
      } else {
        const r = await apiClient.post<{ favorite: Favorite }>('/favorites', { provider: source?.kind === 'demo' ? 'mock' : 'amap', destination: item.destination })
        if (current.current === owner) setFavorites(v => ({ ...v, [id]: r.favorite }))
      }
      if (current.current === owner) setNotice(existing ? '已取消收藏' : '已收藏地点')
    } catch { if (current.current === owner) setNotice('收藏操作失败，请稍后重试。') }
    finally { locks.current.delete(id); setPending(p => p.filter(v => v !== id)) }
  }
  return { favorites: username ? favorites : {}, pending, notice, toggle }
}
