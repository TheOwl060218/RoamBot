import { ChevronLeft, ChevronRight } from 'lucide-react'

import type { RecommendationItem } from '../../api/types'

type MobileCandidateSwitcherProps = {
  items: RecommendationItem[]
  selectedId: string
  visible: boolean
  onSelect: (item: RecommendationItem) => void
  onOpenDrawer: () => void
}

export function MobileCandidateSwitcher({
  items,
  selectedId,
  visible,
  onSelect,
  onOpenDrawer,
}: MobileCandidateSwitcherProps) {
  if (!visible || items.length < 2) return null
  const index = Math.max(0, items.findIndex((item) => item.destination.provider_id === selectedId))
  const current = items[index]
  const previousIndex = (index - 1 + items.length) % items.length
  const nextIndex = (index + 1) % items.length

  return (
    <div className="candidate-switcher" aria-label="切换候选地点">
      <button
        className="icon-button"
        type="button"
        aria-label="上一个地点"
        onClick={() => onSelect(items[previousIndex])}
      >
        <ChevronLeft aria-hidden="true" size={18} />
      </button>
      <button className="candidate-switcher-current" type="button" onClick={onOpenDrawer}>
        <strong>{index + 1}/{items.length}</strong>
        <span>{current.destination.name}</span>
      </button>
      <button
        className="icon-button"
        type="button"
        aria-label="下一个地点"
        onClick={() => onSelect(items[nextIndex])}
      >
        <ChevronRight aria-hidden="true" size={18} />
      </button>
    </div>
  )
}
