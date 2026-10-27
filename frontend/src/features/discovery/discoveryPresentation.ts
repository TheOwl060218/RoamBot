import type { DiscoveryCard } from './types'

export function discoveryTitle(request: string, title?: string | null,
  conversation: readonly { role: string; content: string }[] = [], region?: string | null) {
  if (title?.trim()) return title.trim()
  const text = request.trim()
  const concise = (value: string) => !!value && Array.from(value).length <= 22 && !/[\r\n]/.test(value)
  if (concise(text)) return text
  // Older results have no generated title. Reuse a concise, region-bound user
  // request rather than presenting the expanded search query as a heading.
  const places = region ? [region, region.replace(/[市区县]$/, '')].filter(Boolean) : []
  const original = [...conversation].reverse().find(turn => turn.role === 'user'
    && concise(turn.content.trim()) && places.some(place => turn.content.includes(place)))
  return original?.content.trim() || text || '想去哪儿？'
}

export function placeType(value: string) {
  return [...new Set(value.split(/[;；]/).map(s => s.trim()).filter(Boolean))].slice(-2).join(' · ')
}

export function placeArea(card: DiscoveryCard) {
  return [...new Set([card.place.city, card.place.facts.district].map(value => value?.trim()).filter(Boolean))].join(' · ')
}

export function arrivalCoordinate(card: DiscoveryCard) {
  const entry = card.place.facts.entr_location
  if (typeof entry === 'string' && entry.split(',').length === 2) {
    const [longitude, latitude] = entry.split(',').map(value => value.trim() ? Number(value) : NaN)
    if (Number.isFinite(longitude) && Number.isFinite(latitude) && Math.abs(longitude) <= 180 && Math.abs(latitude) <= 90)
      return { longitude, latitude, system: 'gcj02' }
  }
  return card.place.coordinate
}

export function visitingFacts(card: DiscoveryCard) {
  const facts = card.place.facts
  const rows: { label: string; value: string }[] = []
  const hours = (facts.opentime_today || facts.opentime_week)?.trim()
  if (hours) rows.push({ label: '开放时间', value: hours })
  const cost = facts.cost?.trim()
  if (cost) rows.push({ label: '参考消费', value: /^\d+(\.\d+)?$/.test(cost) ? `¥${cost} / 人` : cost })
  return rows
}

export function routeLabel(card: DiscoveryCard) {
  const route = card.route
  if (!route || route.unavailable || route.distance_km === undefined) return ''
  const modes: Record<string, string> = { walking: '步行', bicycling: '骑行', driving: '驾车' }
  const distance = route.distance_km < 1 ? `${Math.round(route.distance_km * 1000)} 米` : `${Number(route.distance_km.toFixed(1))} 公里`
  return `${modes[route.mode ?? ''] ?? ''} ${distance}${route.duration_minutes === undefined ? '' : ` · 约${Math.round(route.duration_minutes)}分钟`}${arrivalCoordinate(card) !== card.place.coordinate ? ' · 至地图入口' : ''}`.trim()
}

export function weatherLabel(card: DiscoveryCard) {
  const day = Array.isArray(card.weather) ? card.weather[0] : null
  return day ? `${day.date.slice(5).replace('-', '.')} · ${day.condition} · ${day.temp_min_c}–${day.temp_max_c}°C` : ''
}

/** This is an existing activity label, not a new model-written recommendation. */
export function activityLabel(card: DiscoveryCard) {
  const value = card.experience.trim()
  return value && value !== card.place.name && value !== placeType(card.place.map_type) ? value : ''
}
