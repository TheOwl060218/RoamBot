import { useEffect, useState } from 'react'

import { apiClient } from '../api/client'
import type { Favorite } from '../api/types'
import { FavoriteList } from '../features/favorites/FavoriteList'

export function FavoritesPage() {
  const [favorites, setFavorites] = useState<Favorite[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    void apiClient.get<{ favorites: Favorite[] }>('/favorites')
      .then((result) => setFavorites(result.favorites))
      .catch(() => setError('收藏加载失败，请稍后重试。'))
      .finally(() => setLoading(false))
  }, [])

  async function remove(id: string) {
    try {
      await apiClient.delete(`/favorites/${id}`)
      setFavorites((current) => current.filter((favorite) => favorite.id !== id))
    } catch {
      setError('删除收藏失败。')
    }
  }

  return (
    <section className="personal-page">
      <header className="page-heading"><div><p className="eyebrow">个人地点库</p><h1>收藏</h1></div></header>
      {error && <div className="error-banner" role="alert">{error}</div>}
      {loading ? <p className="loading-state">正在加载收藏…</p> : <FavoriteList favorites={favorites} onDelete={remove} />}
    </section>
  )
}
