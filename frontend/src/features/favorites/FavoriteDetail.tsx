import { MapPin, RefreshCcw, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { Favorite } from '../../api/types'
import { scenerySummary } from './favoritePresentation'
import { placeType } from '../discovery/discoveryPresentation'
import { amapPlaceUrl, amapSearchUrl } from '../search/amapLink'
import { AddToItinerary } from '../itineraries/ItineraryProvider'

type FavoriteDetailProps = {
  favorite: Favorite
  onDelete: (id: string) => void
  onClose?: () => void
}

export function FavoriteDetail({ favorite, onDelete, onClose }: FavoriteDetailProps) {
  const { place } = favorite

  return (
    <article className="favorite-detail" aria-labelledby={`favorite-title-${favorite.id}`}>
      <header>
        <div>
          <p className="eyebrow">{place.city} · {scenerySummary(place.scenery_tags)}</p>
          <h2 id={`favorite-title-${favorite.id}`}>{place.name}</h2>
          <p className="favorite-address"><MapPin aria-hidden="true" size={17} />{place.address}</p>
        </div>
        {onClose && <button className="text-button" type="button" onClick={onClose}>← 返回收藏</button>}
      </header>

      <dl className="favorite-facts">
        <div><dt>地点类型</dt><dd>{placeType(place.type_name || '') || scenerySummary(place.scenery_tags)}</dd></div>
        <div><dt>所在城市</dt><dd>{place.city}</dd></div>
        <div><dt>收藏时间</dt><dd>{new Date(favorite.created_at).toLocaleDateString('zh-CN')}</dd></div>
      </dl>


      <div className="favorite-detail-actions">
        <AddToItinerary source={{ favorite_id: favorite.id }} />
        <a className="icon-text-button link-button" href={amapPlaceUrl(`${place.provider}:${place.provider_place_id}`) ?? amapSearchUrl(place.name, place.city)} target="_blank" rel="noreferrer">
          <MapPin aria-hidden="true" size={16} />查看位置
        </a>
        <Link className="icon-text-button link-button primary-action" to="/explore" state={{ initialIdea: `想去${place.city}${place.name}，看看怎样游玩` }} viewTransition>
          <RefreshCcw aria-hidden="true" size={16} />继续探索
        </Link>
        <button className="icon-text-button danger-action" type="button" aria-label={`删除 ${place.name}`} onClick={() => onDelete(favorite.id)}>
          <Trash2 aria-hidden="true" size={16} />取消收藏
        </button>
      </div>
    </article>
  )
}
