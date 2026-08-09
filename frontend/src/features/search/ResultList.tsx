import { useEffect, useRef, useState } from 'react'

import type { RecommendationItem, SceneryType, SourceState } from '../../api/types'
import { CandidateList } from './CandidateList'
import { CandidateDrawer } from './CandidateDrawer'
import { MobileCandidateSwitcher } from './MobileCandidateSwitcher'
import { PlaceDetail } from './PlaceDetail'
import { SourceNotice } from './SourceNotice'

type ResultListProps = {
  items: RecommendationItem[]
  source: SourceState
  generatedAt: string
  uncoveredTypes?: SceneryType[]
  onFavorite?: (item: RecommendationItem) => void
  favoriteIds?: Set<string>
  favoritePendingIds?: Set<string>
  selectedId?: string | null
  onSelect?: (item: RecommendationItem) => void
  candidateSwitcherEnabled?: boolean
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
  favoriteIds = new Set(),
  favoritePendingIds = new Set(),
  selectedId,
  onSelect,
  candidateSwitcherEnabled = true,
}: ResultListProps) {
  const [internalSelectedId, setInternalSelectedId] = useState<string | null>(null)
  const [candidateListVisible, setCandidateListVisible] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const candidateSentinelRef = useRef<HTMLDivElement>(null)
  const requestedId = selectedId ?? internalSelectedId
  const selectedItem = items.find((item) => item.destination.provider_id === requestedId) ?? items[0]

  function select(item: RecommendationItem) {
    setInternalSelectedId(item.destination.provider_id)
    onSelect?.(item)
  }

  useEffect(() => {
    const sentinel = candidateSentinelRef.current
    if (!sentinel) return
    const scrollContainer = sentinel.closest('.candidate-pane')
    const updateFromScroll = () => {
      const headerOffset = window.innerWidth <= 600 ? 104 : 60
      const pageHasMoved = window.scrollY > 96
      const listHasMovedUp = sentinel.getBoundingClientRect().top <= headerOffset + 120
      const listHasScrolled = (scrollContainer?.scrollTop ?? 0) > 16
      setCandidateListVisible(!pageHasMoved && !listHasMovedUp && !listHasScrolled)
    }
    updateFromScroll()
    window.addEventListener('scroll', updateFromScroll, { passive: true })
    window.addEventListener('resize', updateFromScroll)
    scrollContainer?.addEventListener('scroll', updateFromScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', updateFromScroll)
      window.removeEventListener('resize', updateFromScroll)
      scrollContainer?.removeEventListener('scroll', updateFromScroll)
    }
  }, [candidateSwitcherEnabled, items.length])

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
            天气数据来自和风天气；地点评分来自高德开放平台；距离与用时按查询时驾车路况估算；出游匹配指数仅用于比较本次候选地点。
          </p>
          {selectedItem && (
            <div className="results-comparison">
              <div className="candidate-pane">
                <div className="candidate-list-sentinel" ref={candidateSentinelRef} aria-hidden="true" />
                <CandidateList
                  items={items}
                  selectedId={selectedItem.destination.provider_id}
                  onSelect={select}
                />
              </div>
              <div className="detail-pane">
                <PlaceDetail
                  item={selectedItem}
                onFavorite={onFavorite}
                  isFavorite={favoriteIds.has(selectedItem.destination.provider_id)}
                  favoritePending={favoritePendingIds.has(selectedItem.destination.provider_id)}
                />
              </div>
            </div>
          )}
          {selectedItem && (
            <>
              <MobileCandidateSwitcher
                items={items}
                selectedId={selectedItem.destination.provider_id}
                visible={candidateSwitcherEnabled && !candidateListVisible}
                onSelect={select}
                onOpenDrawer={() => setDrawerOpen(true)}
              />
              <CandidateDrawer
                open={candidateSwitcherEnabled && drawerOpen}
                items={items}
                selectedId={selectedItem.destination.provider_id}
                onSelect={select}
                onClose={() => setDrawerOpen(false)}
              />
            </>
          )}
        </>
      )}
    </section>
  )
}
