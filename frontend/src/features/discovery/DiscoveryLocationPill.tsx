import { useEffect, useId, useRef, useState } from 'react'
import { ChevronDown, LocateFixed, MapPin, X } from 'lucide-react'
import type { PlaceSuggestion } from '../../api/types'
import type { DiscoverySnapshot } from './types'
import { PlaceInput } from '../search/PlaceInput'

export function DiscoveryLocationPill({ position, fallback, region, locating, error, onRetry, onSelect, onRegionOnly }: {
  position?: DiscoverySnapshot['position']; fallback?: string | null; locating: boolean; error: string
  region?: string | null; onRegionOnly?: () => void; onRetry: () => void; onSelect: (place: PlaceSuggestion) => void
}) {
  const [open, setOpen] = useState(false), [draft, setDraft] = useState('')
  const root = useRef<HTMLDivElement>(null)
  const optionsId = useId()
  useEffect(() => {
    if (!open) return
    const dismiss = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); root.current?.querySelector('button')?.focus() } }
    document.addEventListener('pointerdown', dismiss); document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', dismiss); document.removeEventListener('keydown', escape) }
  }, [open])
  const label = locating ? '正在获取位置…' : error || (position?.label
    ? `${position.source === 'selected' ? '出发地' : position.source === 'region' ? '推荐地区' : '定位'}：${position.label}` : fallback || (region ? `推荐地区：${region}` : '位置'))
  return <div ref={root} className='discovery-location-control'>
    <button type='button' className='discovery-location-pill' aria-label={`修改位置：${label}`} aria-expanded={open} aria-controls={optionsId}
      onClick={() => setOpen(value => !value)}><MapPin size={14} aria-hidden='true' />
      <span role='status'>{label}</span><ChevronDown size={12} aria-hidden='true' /></button>
    {open && <section id={optionsId} className='discovery-location-options' aria-label='修改位置'>
      <div className='discovery-location-title'><strong>从哪里出发</strong>
        <button type='button' className='icon-button' aria-label='关闭位置选择' onClick={() => setOpen(false)}><X size={15} /></button></div>
      <button type='button' className='text-button' disabled={locating} onClick={() => { setOpen(false); onRetry() }}><LocateFixed size={14} />重新定位</button>
      {onRegionOnly && region && <button type='button' className='text-button' disabled={locating} onClick={() => { setOpen(false); onRegionOnly() }}>只按{region}推荐</button>}
      <PlaceInput label='选择出发位置' value={draft} city='' placeholder='搜索车站、地标或附近地点' onChange={setDraft}
        onSuggestionSelect={place => { if (place.coordinate) { onSelect(place); setOpen(false); setDraft('') } }} />
      {position?.accuracy_m != null && <small>设备估计范围约 {position.accuracy_m >= 1000 ? `${(position.accuracy_m / 1000).toFixed(1)} 千米` : `${Math.round(position.accuracy_m)} 米`}</small>}
    </section>}
  </div>
}
