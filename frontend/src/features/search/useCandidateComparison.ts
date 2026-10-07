import { useState } from 'react'

import type { RecommendationItem } from '../../api/types'
import { compareCandidates } from './compareLogic'

const MAX_SELECTED = 3

export function useCandidateComparison(items: RecommendationItem[]) {
  const [storedSelectedIds, setStoredSelectedIds] = useState<string[]>([])
  const availableIds = new Set(items.map((item) => item.destination.provider_id))
  const selectedIds = storedSelectedIds.filter((id) => availableIds.has(id))
  if (items.length < 2) {
    return {
      items,
      selectedIds,
      selectedItems: [] as RecommendationItem[],
      canCompare: false,
      result: null as ReturnType<typeof compareCandidates> | null,
      toggle: () => {},
      reset: () => setStoredSelectedIds([]),
    }
  }
  const selectedItems = items.filter((item) => selectedIds.includes(item.destination.provider_id))
  const originCount = selectedItems[0]?.distances.length ?? 1
  const result = selectedItems.length >= 2 ? compareCandidates(selectedItems, originCount) : null
  function toggle(id: string) {
    setStoredSelectedIds((current) => {
      const availableCurrent = current.filter((value) => availableIds.has(value))
      if (availableCurrent.includes(id)) return availableCurrent.filter((value) => value !== id)
      if (availableCurrent.length >= MAX_SELECTED) return availableCurrent
      return [...availableCurrent, id]
    })
  }
  return { items, selectedIds, selectedItems, canCompare: true, result, toggle, reset: () => setStoredSelectedIds([]) }
}
