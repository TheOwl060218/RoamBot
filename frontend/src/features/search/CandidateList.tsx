import { MapPin, Star } from 'lucide-react'

import type { RecommendationItem } from '../../api/types'
import { tripMatchIndex } from './matchLabels'

type CandidateListProps = {
  items: RecommendationItem[]
  selectedId: string
  onSelect: (item: RecommendationItem) => void
}

const adviceLabels = {
  suitable: '适合前往',
  some_dates_caution: '部分日期需谨慎',
  some_dates_not_recommended: '部分日期不建议',
} as const

export function CandidateList({ items, selectedId, onSelect }: CandidateListProps) {
  return (
    <nav className="candidate-list" aria-label="候选地点">
      <ol>
        {items.map((item, index) => {
          const selected = item.destination.provider_id === selectedId
          const distance = item.group_accessibility.average_distance_km
          return (
            <li key={item.destination.provider_id}>
              <button
                type="button"
                className="candidate-row"
                aria-current={selected ? 'true' : undefined}
                onClick={() => onSelect(item)}
              >
                <span className="candidate-rank">{index + 1}</span>
                <span className="candidate-copy">
                  <strong>{item.destination.name}</strong>
                  <span><MapPin aria-hidden="true" size={14} />{distance.toFixed(1)} km</span>
                  <small>{adviceLabels[item.overall_advice]}</small>
                </span>
                <span className="candidate-score">
                  <strong>{tripMatchIndex(item.score.total)}</strong>
                  <span>{item.destination.rating === null ? '暂无评分' : <><Star aria-hidden="true" size={12} />{item.destination.rating.toFixed(1)}</>}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
