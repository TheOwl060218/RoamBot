import { useEffect, useState } from 'react'
import { OverlayHost } from '../features/studio/OverlayHost'

import { apiClient } from '../api/client'
import type { Favorite } from '../api/types'
import { FavoriteDetail } from '../features/favorites/FavoriteDetail'
import { FavoriteList } from '../features/favorites/FavoriteList'
import { useBusinessRevision } from '../features/commands/commandEvents'
import { useBusinessAssistant, useCommandTarget } from '../features/commands/commandContext'

export function FavoritesPage() {
  const business = useBusinessAssistant()
  const businessRevision = useBusinessRevision()
  const [favorites, setFavorites] = useState<Favorite[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    void apiClient.get<{ favorites: Favorite[] }>('/favorites')
      .then((result) => setFavorites(result.favorites))
      .catch(() => setError('收藏加载失败，请稍后重试。'))
      .finally(() => setLoading(false))
  }, [businessRevision])

  async function remove(id: string) {
    try {
      const removed = favorites.find((favorite) => favorite.id === id)
      await apiClient.delete(`/favorites/${id}`)
      setFavorites((current) => current.filter((favorite) => favorite.id !== id))
      if (removed) setToast(`已取消收藏${removed.place.name}。`)
    } catch {
      setError('删除收藏失败。')
    }
  }

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(''), 2400)
    return () => window.clearTimeout(timer)
  }, [toast])

  const selected = favorites.find((favorite) => favorite.id === selectedId) ?? null
  useCommandTarget('favorites', () => ({ focused_id: selectedId,
    visible_resources: { kind: 'favorites', ids: favorites.slice(0, 100).map(item => item.id) },
    layer: selected ? 'favorite-detail' : 'favorites' }), effect => {
    if (effect.tool === 'open_detail') {
      const id = String(effect.arguments.id)
      if (!favorites.some(f => f.id === id)) throw new Error('收藏已变化。')
      setSelectedId(id)
    } else if (effect.tool === 'close_layer' && selected) setSelectedId(null)
    else return false
    return true
  })

  return (
    <section className="personal-page">
      <header className="page-heading"><div><p className="eyebrow">个人地点库</p><h1>收藏</h1></div></header>
      {error && <div className="error-banner" role="alert">{error}</div>}
      {loading ? <p className="loading-state">正在加载收藏…</p> : favorites.length ? (
        <div className="favorites-workspace">
          <FavoriteList favorites={favorites} selectedId={selected?.id ?? null} onSelect={setSelectedId} />
          {selected && <OverlayHost label={`${selected.place.name}收藏详情`} onClose={() => setSelectedId(null)} className='favorite-detail-layer' panelClassName='favorite-detail-host' accessory={business?.chat}>
            <FavoriteDetail favorite={selected} onClose={() => setSelectedId(null)} onDelete={remove} />
          </OverlayHost>}
        </div>
      ) : <p className="empty-state">还没有收藏地点。完成一次推荐后即可收藏。</p>}
      {toast && <div className="app-toast" role="status">{toast}</div>}
    </section>
  )
}
