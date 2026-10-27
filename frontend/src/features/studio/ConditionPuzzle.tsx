import { useEffect, useState } from 'react'
import type { ConditionKey, StudioState } from './types'
import { loadRegionCatalog, type RegionCatalog } from '../search/regions'

import { projectConditionCards, projectResultRail } from './conditionProjection'
export function ConditionPuzzle({ state, onEdit, onRemove, onOther, layout = 'corner' }: { state: StudioState; onEdit: (key: ConditionKey) => void; onRemove?: (key: ConditionKey) => void; onOther?: () => void; layout?: 'corner' | 'compact' }) {
  const d = state.draft
  const [catalog, setCatalog] = useState<RegionCatalog | null>(null)
  const hasRegions = !!d.destinationRegions?.length
  useEffect(() => {
    if (!hasRegions) return
    let alive = true
    void loadRegionCatalog().then(value => { if (alive) setCatalog(value) }).catch(() => undefined)
    return () => { alive = false }
  }, [hasRegions])
  const regionNames = d.destinationRegions?.slice(0, 2).map(code => catalog?.regions.find(r => r.adcode === code)?.name ?? '地区待确认').join(' · ')
  const cards = projectConditionCards(state).map(card => card.key === 'range' && hasRegions ? { ...card, value: `${regionNames}${d.destinationRegions!.length > 2 ? ` · +${d.destinationRegions!.length - 2}` : ''}` } : card)
  const visible = layout === 'compact' ? projectResultRail(cards) : cards
  return <section className={`condition-puzzle condition-puzzle-${layout}`} aria-label='当前出行条件'>
    {visible.map(card => <div className='condition-piece' key={card.id} data-condition-id={card.id}>
      <button className='condition-piece-edit' type='button' onClick={() => card.id === 'otherPreferences' && onOther ? onOther() : onEdit(card.key)} aria-label={`编辑${card.label}：${card.value}`}>
        <small>{card.label}</small><span>{card.value}</span>
      </button>
      {onRemove && card.id !== 'otherPreferences' && <button className='condition-piece-remove' type='button' aria-label={`移除${card.label}`} onClick={() => onRemove(card.key)}>×</button>}
    </div>)}
  </section>
}
