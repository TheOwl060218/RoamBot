import type { RecommendationItem, SceneryType, SourceState } from '../../api/types'
import { ResultCard } from './ResultCard'
import { SourceNotice } from './SourceNotice'

type ResultListProps = {
  items: RecommendationItem[]
  source: SourceState
  generatedAt: string
  uncoveredTypes?: SceneryType[]
  onFavorite?: (item: RecommendationItem) => void
}

const sceneryLabels: Record<SceneryType, string> = {
  lake: '湖景',
  sea: '海景',
  old_town: '古镇/历史街区',
  museum: '博物馆',
  park: '公园/绿地/湿地',
  mountain: '山地/徒步',
}

export function ResultList({
  items,
  source,
  generatedAt,
  uncoveredTypes = [],
  onFavorite,
}: ResultListProps) {
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
      {uncoveredTypes.length > 0 && (
        <p className="coverage-notice">
          暂未找到可覆盖以下偏好的合适地点：
          {uncoveredTypes.map((type) => sceneryLabels[type]).join('、')}。
        </p>
      )}
      {items.length === 0 ? (
        <p className="empty-state">可以尝试增加最大距离、调整日期或更换风景类型。</p>
      ) : (
        <>
          <p className="result-method-note">
            地点评分数据来源：高德开放平台；出游匹配指数仅用于比较本次候选地点，不代表官方评价。
          </p>
          <div className="result-list">
            {items.map((item) => (
              <ResultCard key={item.destination.provider_id} item={item} onFavorite={onFavorite} />
            ))}
          </div>
        </>
      )}
    </section>
  )
}
