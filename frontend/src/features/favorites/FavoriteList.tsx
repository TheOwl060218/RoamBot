import { RefreshCcw, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { Favorite } from '../../api/types'

export function FavoriteList({ favorites, onDelete }: { favorites: Favorite[]; onDelete: (id: string) => void }) {
  if (!favorites.length) return <p className="empty-state">还没有收藏地点。完成一次推荐后即可收藏。</p>
  return (
    <div className="personal-list">
      {favorites.map((favorite) => (
        <article className="personal-item" key={favorite.id}>
          <div>
            <p className="eyebrow">{favorite.place.city} · {favorite.place.type_name}</p>
            <h2>{favorite.place.name}</h2>
            <p>{favorite.place.address}</p>
          </div>
          <div className="item-actions">
            <Link
              className="icon-text-button link-button"
              to="/"
              state={{ evaluationTarget: favorite.place.name }}
            >
              <RefreshCcw aria-hidden="true" size={16} />重新评估
            </Link>
            <button className="icon-button" type="button" aria-label={`删除 ${favorite.place.name}`} onClick={() => onDelete(favorite.id)}>
              <Trash2 aria-hidden="true" size={17} />
            </button>
          </div>
        </article>
      ))}
    </div>
  )
}
