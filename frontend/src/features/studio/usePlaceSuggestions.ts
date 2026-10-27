import { useEffect, useRef, useState } from 'react'

import { apiClient } from '../../api/client'
import type { PlaceSuggestion } from '../../api/types'

const cache = new Map<string, PlaceSuggestion[]>()

function canSearch(value: string) {
  const minimum = /[\u3400-\u9fff]/.test(value) ? 2 : 3
  return Array.from(value).length >= minimum
}

export function usePlaceSuggestions({ value, city, enabled }: { value: string; city: string; enabled: boolean }) {
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const sequence = useRef(0)

  useEffect(() => {
    const keywords = value.trim()
    const current = ++sequence.current
    if (!enabled || !canSearch(keywords)) {
      queueMicrotask(() => { setSuggestions([]); setLoading(false); setError('') })
      return
    }
    const key = `${city.trim()}|${keywords}`
    const cached = cache.get(key)
    if (cached) {
      queueMicrotask(() => { if (current === sequence.current) { setSuggestions(cached); setLoading(false); setError('') } })
      return
    }
    queueMicrotask(() => { if (current === sequence.current) { setLoading(true); setError('') } })
    const timer = window.setTimeout(() => {
      void apiClient.get<{ suggestions: PlaceSuggestion[] }>(`/places/suggestions?keywords=${encodeURIComponent(keywords)}&city=${encodeURIComponent(city.trim())}`)
        .then(response => {
          if (current !== sequence.current) return
          const next = response.suggestions.slice(0, 5)
          cache.set(key, next)
          setSuggestions(next)
          setLoading(false)
        })
        .catch(() => {
          if (current !== sequence.current) return
          setSuggestions([])
          setLoading(false)
          setError('地点候选暂时不可用，可直接输入后保存。')
        })
    }, 450)
    return () => window.clearTimeout(timer)
  }, [city, enabled, value])

  return { suggestions, loading, error }
}
