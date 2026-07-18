import type { RecommendationItem, SourceState } from '../../api/types'
import { ResultCard } from './ResultCard'
import { SourceNotice } from './SourceNotice'

type ResultListProps = {
  items: RecommendationItem[]
  source: SourceState
  generatedAt: string
  onFavorite?: (item: RecommendationItem) => void
}

export function ResultList({ items, source, generatedAt, onFavorite }: ResultListProps) {
  return (
    <section className="results-panel" aria-live="polite">
      <div className="results-heading">
        <div>
          <p className="eyebrow">查询结果</p>
          <h2>{items.length ? `${items.length} 个地点值得考虑` : '规定范围内无检索结果'}</h2>
        </div>
        <time dateTime={generatedAt}>{new Date(generatedAt).toLocaleString('zh-CN')}</time>
      </div>
      <SourceNotice source={source} />
      {items.length === 0 ? (
        <p className="empty-state">可以尝试增加最大距离、调整日期或更换风景类型。</p>
      ) : (
        <div className="result-list">
          {items.map((item) => (
            <ResultCard key={item.destination.provider_id} item={item} onFavorite={onFavorite} />
          ))}
        </div>
      )}
    </section>
  )
}
