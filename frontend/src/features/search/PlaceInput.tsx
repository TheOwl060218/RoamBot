import { useEffect, useId, useRef, useState } from 'react'

import { apiClient } from '../../api/client'
import type { PlaceSuggestion } from '../../api/types'

const suggestionCache = new Map<string, PlaceSuggestion[]>()

type PlaceInputProps = {
  label: string
  value: string
  city: string
  placeholder?: string
  error?: string
  onChange: (value: string) => void
  onSuggestionSelect?: (suggestion: PlaceSuggestion) => void
}

export function PlaceInput({
  label,
  value,
  city,
  placeholder,
  error,
  onChange,
  onSuggestionSelect,
}: PlaceInputProps) {
  const inputId = useId()
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([])
  const [open, setOpen] = useState(false)
  const requestSequence = useRef(0)
  const selectedValue = useRef('')
  const focused = useRef(false)
  const userEdited = useRef(false)
  const previousCity = useRef(city)

  useEffect(() => {
    const keywords = value.trim()
    const sequence = ++requestSequence.current
    if (previousCity.current !== city) {
      previousCity.current = city
      userEdited.current = false
      queueMicrotask(() => {
        setSuggestions([])
        setOpen(false)
      })
      return
    }
    if (selectedValue.current === keywords) {
      selectedValue.current = ''
      return
    }
    if (!focused.current || !userEdited.current) return
    if (!hasEnoughKeywords(keywords)) {
      queueMicrotask(() => {
        setSuggestions([])
        setOpen(false)
      })
      return
    }
    const key = `${city.trim()}|${keywords}`
    const cached = suggestionCache.get(key)
    if (cached) {
      queueMicrotask(() => {
        setSuggestions(cached)
        setOpen(focused.current && userEdited.current && cached.length > 0)
      })
      return
    }
    const timer = window.setTimeout(() => {
      void apiClient.get<{ suggestions: PlaceSuggestion[] }>(
        `/places/suggestions?keywords=${encodeURIComponent(keywords)}&city=${encodeURIComponent(city.trim())}`,
      ).then((response) => {
        if (sequence !== requestSequence.current) return
        const values = response.suggestions.slice(0, 5)
        suggestionCache.set(key, values)
        setSuggestions(values)
        setOpen(focused.current && userEdited.current && values.length > 0)
      }).catch(() => {
        if (sequence === requestSequence.current) setOpen(false)
      })
    }, 450)
    return () => window.clearTimeout(timer)
  }, [city, value])

  return (
    <div className="field place-input">
      <label htmlFor={inputId}>{label}</label>
      <input
        id={inputId}
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={open}
        onChange={(event) => {
          const next = event.target.value
          userEdited.current = true
          if (!hasEnoughKeywords(next.trim())) setOpen(false)
          onChange(next)
        }}
        onFocus={() => {
          focused.current = true
        }}
        onBlur={() => {
          focused.current = false
          window.setTimeout(() => setOpen(false), 120)
        }}
      />
      {open && (
        <div className="place-suggestions" role="listbox" aria-label={`${label}候选项`}>
          {suggestions.map((suggestion) => (
            <button
              type="button"
              role="option"
              aria-selected="false"
              key={`${suggestion.provider_id}:${suggestion.name}:${suggestion.address}`}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                selectedValue.current = suggestion.name
                userEdited.current = false
                onChange(suggestion.name)
                onSuggestionSelect?.(suggestion)
                setOpen(false)
              }}
            >
              <strong>{suggestion.name}</strong>
              <span>{[suggestion.district, suggestion.address].filter(Boolean).join(' · ')}</span>
            </button>
          ))}
        </div>
      )}
      <span className="field-message">{error && <small className="field-error">{error}</small>}</span>
    </div>
  )
}

function hasEnoughKeywords(value: string) {
  const minimum = /[\u3400-\u9fff]/.test(value) ? 2 : 3
  return Array.from(value).length >= minimum
}
