import { Clock3, Heart, MapPin } from 'lucide-react'

import type { RecommendationItem } from '../../api/types'
import { DailyWeatherList } from './DailyWeatherList'

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
        <div className="score-total" aria-label={`综合推荐指数 ${score.total.toFixed(1)}`}>
          <strong>{score.total.toFixed(1)}</strong>
          <span>推荐指数</span>
        </div>
      </header>

      <div className="score-grid" aria-label="分项评分">
        <div><span>天气</span><strong>{score.weather.toFixed(1)}</strong></div>
        <div><span>距离</span><strong>{score.distance.toFixed(1)}</strong></div>
        <div><span>公平性</span><strong>{score.fairness.toFixed(1)}</strong></div>
        <div><span>RoamBot 热度估算</span><strong>{score.popularity.toFixed(1)}</strong></div>
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
