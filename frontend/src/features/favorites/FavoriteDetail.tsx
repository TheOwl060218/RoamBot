import { MapPin, RefreshCcw, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { Favorite } from '../../api/types'
import { scenerySummary } from './favoritePresentation'

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
        <div><dt>地点类型</dt><dd>{place.type_name || scenerySummary(place.scenery_tags)}</dd></div>
        <div><dt>所在城市</dt><dd>{place.city}</dd></div>
        <div><dt>收藏时间</dt><dd>{new Date(favorite.created_at).toLocaleDateString('zh-CN')}</dd></div>
      </dl>


      <div className="favorite-detail-actions">
        <Link className="icon-text-button link-button primary-action" to="/recommend" state={{ evaluationTarget: place.name }}>
          <RefreshCcw aria-hidden="true" size={16} />重新评估
        </Link>
        <button className="icon-text-button danger-action" type="button" aria-label={`删除 ${place.name}`} onClick={() => onDelete(favorite.id)}>
          <Trash2 aria-hidden="true" size={16} />取消收藏
        </button>
      </div>
    </article>
  )
}
