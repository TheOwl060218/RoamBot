import type { Favorite } from '../../api/types'
import { MapPin } from 'lucide-react'
import { scenerySummary } from './favoritePresentation'
import { placeType } from '../discovery/discoveryPresentation'
import { AddToItinerary } from '../itineraries/ItineraryProvider'

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
        <article className='favorite-card' key={favorite.id} aria-label={`${favorite.place.name}收藏卡片`}>
        <button
          className="favorite-list-item"
          type="button"
          aria-label={`查看 ${favorite.place.name}`}
          aria-pressed={favorite.id === selectedId}
          onClick={() => onSelect(favorite.id)}
        />
          <header className='favorite-card-meta'>
            <span>{favorite.place.scenery_tags.length ? scenerySummary(favorite.place.scenery_tags) : placeType(favorite.place.type_name)}</span>
            <time dateTime={favorite.created_at} title={new Date(favorite.created_at).toLocaleDateString('zh-CN')}>
              {new Date(favorite.created_at).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })} 收藏
            </time>
          </header>
          <strong className='favorite-card-name'>{favorite.place.name}</strong>
          <p className='favorite-card-city'><MapPin size={14} aria-hidden='true' />{favorite.place.city}</p>
          {favorite.place.address && favorite.place.address !== favorite.place.name && <p className='favorite-card-address'>{favorite.place.address}</p>}
          <footer className='favorite-card-actions'><AddToItinerary source={{ favorite_id: favorite.id }} /></footer>
        </article>
      ))}
    </div>
  )
}
