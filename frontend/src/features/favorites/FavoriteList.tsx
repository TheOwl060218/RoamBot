import type { Favorite } from '../../api/types'
import { scenerySummary } from './favoritePresentation'

type FavoriteListProps = {
  favorites: Favorite[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function FavoriteList({ favorites, selectedId, onSelect }: FavoriteListProps) {
  if (!favorites.length) return <p className="empty-state">还没有收藏地点。完成一次推荐后即可收藏。</p>
  return (
    <div className="favorite-list" aria-label="收藏地点列表">
      {favorites.map((favorite) => (
        <button
          className="favorite-list-item"
          type="button"
          key={favorite.id}
          aria-label={`查看 ${favorite.place.name}`}
          aria-pressed={favorite.id === selectedId}
          onClick={() => onSelect(favorite.id)}
        >
          <strong>{favorite.place.name}</strong>
          <span>{favorite.place.city} · {scenerySummary(favorite.place.scenery_tags)}</span>
          <small>{favorite.place.address}</small>
        </button>
      ))}
    </div>
  )
}
