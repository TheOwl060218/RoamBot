import { useId, useState } from 'react'

import type { PlaceSuggestion } from '../../api/types'
import { usePlaceSuggestions } from './usePlaceSuggestions'

export function StudioPlaceField({ label, value, city, onChange, onSelect }: {
  label: string; value: string; city: string; onChange: (text: string) => void; onSelect: (place: PlaceSuggestion) => void
}) {
  const id = useId()
  const [focused, setFocused] = useState(false)
  const [active, setActive] = useState(0)
  const { suggestions, loading, error } = usePlaceSuggestions({ value, city, enabled: focused })
  const open = focused && suggestions.length > 0
  function choose(place: PlaceSuggestion) {
    onChange(place.name)
    onSelect(place)
    setFocused(false)
  }
  return <div className='studio-place-field'>
    <label htmlFor={id}>{label}</label>
    <input id={id} role='combobox' autoFocus autoComplete='off' aria-autocomplete='list' aria-expanded={open}
      aria-controls={open ? `${id}-options` : undefined} value={value} placeholder='输入车站、学校或详细地点'
      onFocus={() => setFocused(true)} onBlur={() => window.setTimeout(() => setFocused(false), 100)}
      onChange={event => { onChange(event.target.value); setActive(0) }}
      onKeyDown={event => {
        if (event.nativeEvent.isComposing) return
        if (event.key === 'ArrowDown' && open) { event.preventDefault(); setActive(index => Math.min(index + 1, suggestions.length - 1)) }
        if (event.key === 'ArrowUp' && open) { event.preventDefault(); setActive(index => Math.max(index - 1, 0)) }
        if (event.key === 'Enter' && open) { event.preventDefault(); choose(suggestions[active]) }
      }} />
    {loading && <small className='studio-place-status'>正在寻找地点…</small>}
    {error && <small className='studio-place-status'>{error}</small>}
    {open && <div className='studio-place-options' id={`${id}-options`} role='listbox' aria-label={`${label}候选项`}>
      {suggestions.map((place, index) => <button type='button' role='option' aria-selected={index === active}
        key={`${place.provider_id}:${place.name}:${place.address}`} onMouseDown={event => event.preventDefault()} onClick={() => choose(place)}>
        <strong>{place.name}</strong><span>{[place.district, place.address].filter(Boolean).join(' · ')}</span>
      </button>)}
    </div>}
  </div>
}
