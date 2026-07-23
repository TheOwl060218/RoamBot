import { Clock3, Heart, MapPin } from 'lucide-react'

import type { RecommendationItem } from '../../api/types'
import { DailyWeatherList } from './DailyWeatherList'
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

type ResultCardProps = {
  item: RecommendationItem
  onFavorite?: (item: RecommendationItem) => void
}

export function ResultCard({ item, onFavorite }: ResultCardProps) {
  const { destination, score } = item
  const index = tripMatchIndex(score.total)
  const isGroup = item.distances.length > 1
  return (
    <article className="result-card">
      <header className="result-header">
        <div>
          <div className="tag-row">
            {destination.scenery_tags.map((tag) => <span key={tag}>{sceneryLabels[tag] ?? tag}</span>)}
          </div>
          <h2>{destination.name}</h2>
          <p className="destination-address"><MapPin aria-hidden="true" size={16} />{destination.address}</p>
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
        {isGroup && <div><span>同行均衡</span><strong>{fairnessMatchLabel(score.fairness)}</strong></div>}
        <div>
          <span>地点评分</span>
          <strong>
            {destination.rating === null ? '暂无数据' : `${destination.rating.toFixed(1)} / 5`}
          </strong>
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
        <button className="icon-text-button" type="button" onClick={() => onFavorite(item)}>
          <Heart aria-hidden="true" size={17} />收藏地点
        </button>
      )}
    </article>
  )
}
