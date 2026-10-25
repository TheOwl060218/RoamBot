import { useEffect, useRef, useState, type ReactNode } from 'react'

import type { RecommendationItem, SceneryType, SourceState } from '../../api/types'
import { CandidateDrawer } from './CandidateDrawer'
import { MobileCandidateSwitcher } from './MobileCandidateSwitcher'
import { PlaceDetail } from './PlaceDetail'
import { SourceNotice } from './SourceNotice'
import { useBusinessAssistant, useCommandTarget } from '../commands/commandContext'

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
  comparison?: ReactNode
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
  comparison,
}: ResultListProps) {
  const [internalSelectedId, setInternalSelectedId] = useState<string | null>(null)
  const [switcherVisible, setSwitcherVisible] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const topRef = useRef<HTMLDivElement>(null)
  const requestedId = selectedId ?? internalSelectedId
  const selectedItem = items.find((item) => item.destination.provider_id === requestedId) ?? items[0]

  function select(item: RecommendationItem) {
    setInternalSelectedId(item.destination.provider_id)
    onSelect?.(item)
  }
  const business = useBusinessAssistant()
  useCommandTarget('result-list', () => ({ focused_id: selectedItem?.destination.provider_id,
    visible_places: items.map(item => ({ id: item.destination.provider_id, name: item.destination.name })),
  }), async effect => {
    if (effect.tool === 'show_candidates') setDrawerOpen(true)
    else if (effect.tool === 'open_detail' || effect.tool === 'open_map') {
      const item = items.find(i => i.destination.provider_id === effect.arguments.id)
      if (!item) throw new Error('地点已变化。')
      if (item !== selectedItem) {
        select(item)
        if (effect.tool === 'open_map') {
          await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
          await business?.bridge.perform(effect)
        }
      } else if (effect.tool === 'open_map') return false
    } else if (effect.tool === 'close_layer' && drawerOpen) setDrawerOpen(false)
    else return false
    return true
  })

  useEffect(() => {
    const updateFromScroll = () => {
      const pageHasMoved = window.scrollY > 96
      setSwitcherVisible(candidateSwitcherEnabled && pageHasMoved && (window.innerWidth <= 1024))
    }
    updateFromScroll()
    window.addEventListener('scroll', updateFromScroll, { passive: true })
    window.addEventListener('resize', updateFromScroll)
    return () => {
      window.removeEventListener('scroll', updateFromScroll)
      window.removeEventListener('resize', updateFromScroll)
    }
  }, [candidateSwitcherEnabled, items.length])

  return (
    <section className="results-panel" aria-live="polite">
      <div className="results-heading">
        <div>
          
          <h2>{items.length ? `${items.length} 个推荐地点` : '暂未找到合适地点'}</h2>
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
          {selectedItem && (
            <div className="results-detail">
              <div className="detail-pane">
                <div ref={topRef} />
                <PlaceDetail
                  item={selectedItem}
                  mapItems={items}
                  onMapSelect={select}
                  onFavorite={onFavorite}
                  isFavorite={favoriteIds.has(selectedItem.destination.provider_id)}
                  favoritePending={favoritePendingIds.has(selectedItem.destination.provider_id)}
                />
                {comparison}
              </div>
            </div>
          )}
          {selectedItem && (
            <>
              <MobileCandidateSwitcher
                items={items}
                selectedId={selectedItem.destination.provider_id}
                visible={switcherVisible && candidateSwitcherEnabled}
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
