import { Clock3, ExternalLink, MapPin, Star } from 'lucide-react'
import { useMemo, useState } from 'react'
import { LocationMapDialog } from './LocationMapDialog'
import { amapPlaceUrl, amapSearchUrl } from './amapLink'

import type { RecommendationItem } from '../../api/types'
import { DailyWeatherList } from './DailyWeatherList'
import { AmapLogo } from '../../components/AmapLogo'
import { useBusinessAssistant, useCommandTarget } from '../commands/commandContext'
import {
  distanceMatchLabel,
  fairnessMatchLabel,
  tripMatchIndex,
  weatherMatchLabel,
} from './matchLabels'

const adviceLabels = {
  suitable: '适合前往',
  some_dates_caution: '部分日期需谨慎',
  some_dates_not_recommended: '部分日期不建议前往',
} as const

const sceneryLabels: Record<string, string> = {
  lake: '湖景',
  sea: '海景',
  old_town: '古镇',
  museum: '博物馆',
  park: '公园',
  mountain: '山地',
}

type PlaceDetailProps = {
  item: RecommendationItem
  onFavorite?: (item: RecommendationItem) => void
  isFavorite?: boolean
  favoritePending?: boolean
  mapItems?: RecommendationItem[]
  onMapSelect?: (item: RecommendationItem) => void
}

export function PlaceDetail({ item, onFavorite, isFavorite = false, favoritePending = false, mapItems, onMapSelect }: PlaceDetailProps) {
  const business = useBusinessAssistant()
  const [mapOpen, setMapOpen] = useState(false)
  const candidates = useMemo(() => mapItems ?? [item], [mapItems, item])
  const { destination, score } = item
  const index = tripMatchIndex(score.total)
  const isGroup = item.distances.length > 1
  const mapUrl = amapPlaceUrl(destination.provider_id)
  useCommandTarget('place-detail-' + destination.provider_id, () => ({
    layer: mapOpen ? 'map' : 'detail',
  }), effect => {
    if (effect.tool === 'open_map' && effect.arguments.id === destination.provider_id) setMapOpen(true)
    else if (effect.tool === 'close_layer' && mapOpen) setMapOpen(false)
    else if (effect.tool === 'open_external_map' && effect.arguments.id === destination.provider_id) {
      const opened = window.open(amapSearchUrl(destination.name, destination.city), '_blank')
      if (opened) opened.opener = null
      else throw new Error('浏览器拦截了新窗口。')
    } else return false
    return true
  })
  return (
    <article className={`place-detail result-card result-card-${item.overall_advice}`}>
      <header className="result-header">
        <div>
          <div className="tag-row">
            {destination.scenery_tags.map((tag) => <span key={tag}>{sceneryLabels[tag] ?? tag}</span>)}
          </div>
          <h2>{destination.name}</h2>
          <p className="destination-address"><MapPin aria-hidden="true" size={16} />{destination.address}</p>
          <div className="place-map-actions">
            <button className="text-button place-map-link" type="button" onClick={() => setMapOpen(true)} title="在本页查看景点位置"><AmapLogo />查看位置</button>
            {mapUrl && <a className="text-button place-map-link" href={amapSearchUrl(destination.name, destination.city)} target="_blank" rel="noopener noreferrer" title="在高德查看地点"><ExternalLink aria-hidden="true" size={15} />打开高德</a>}
          </div>
        </div>
        <div className="match-index" aria-label={`出游匹配指数 ${index}`}>
          <strong>{index}</strong>
          <span>出游匹配指数</span>
        </div>
      </header>

      <div className={`travel-advice travel-advice-${item.overall_advice}`}>
        <span>出行建议</span>
        <strong>{adviceLabels[item.overall_advice]}</strong>
      </div>

      <div className={`match-grid${isGroup ? ' match-grid-group' : ''}`} aria-label="匹配因素">
        <div><span>天气适配</span><strong>{weatherMatchLabel(score.weather)}</strong></div>
        <div><span>路程体验</span><strong>{distanceMatchLabel(score.distance)}</strong></div>
        {isGroup && <div><span>出行差异</span><strong>{fairnessMatchLabel(score.fairness)}</strong></div>}
        <div>
          <span>地点评分</span>
          <strong>{destination.rating === null ? '暂无数据' : `${destination.rating.toFixed(1)} / 5`}</strong>
        </div>
      </div>

      <div className="distance-list">
        {item.distances.map((distance) => (
          <span key={distance.origin_label}>
            <MapPin aria-hidden="true" size={15} />
            {distance.origin_label} {distance.distance_km.toFixed(2)} km
            {distance.duration_minutes !== null && (
              <><Clock3 aria-hidden="true" size={15} />约 {Math.round(distance.duration_minutes)} 分钟</>
            )}
            {distance.estimated && <em>直线估算</em>}
          </span>
        ))}
      </div>

      <DailyWeatherList weather={item.weather} suitability={item.daily_suitability} />

      <div className="recommendation-copy">
        <h3>推荐理由</h3>
        <p>{item.explanation}</p>
      </div>

      {onFavorite && (
        <button
          className={`icon-text-button favorite-button${isFavorite ? ' favorite-button-active' : ''}`}
          type="button"
          disabled={favoritePending}
          aria-pressed={isFavorite}
          onClick={() => onFavorite(item)}
        >
          <Star aria-hidden="true" fill={isFavorite ? 'currentColor' : 'none'} size={18} />
          {isFavorite ? '取消收藏' : '收藏地点'}
        </button>
      )}
      {mapOpen && <LocationMapDialog items={candidates} selectedId={destination.provider_id} onSelect={onMapSelect} onClose={() => setMapOpen(false)}>{business?.chat}</LocationMapDialog>}
    </article>
  )
}
