import type { RankingWeights, SearchMode } from '../../api/types'

const STORAGE_KEY = 'roambot.ui.display-weights.v2'

export type DisplayWeights = Pick<RankingWeights, 'weather' | 'distance' | 'popularity'>

export const defaultDisplayWeights: DisplayWeights = {
  weather: 40,
  distance: 30,
  popularity: 30,
}

type StoredPreferences = Record<string, DisplayWeights>

export function loadWeightPreference(mode: SearchMode, originCount: 1 | 2 | 3) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const stored = JSON.parse(raw) as StoredPreferences
    const value = stored[preferenceKey(mode, originCount)]
    return isDisplayWeights(value) ? value : null
  } catch {
    return null
  }
}

export function saveWeightPreference(
  mode: SearchMode,
  originCount: 1 | 2 | 3,
  value: DisplayWeights,
) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const stored = raw ? JSON.parse(raw) as StoredPreferences : {}
    stored[preferenceKey(mode, originCount)] = value
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
  } catch {
    // Preferences are optional when storage is unavailable or malformed.
  }
}

function preferenceKey(mode: SearchMode, originCount: 1 | 2 | 3) {
  return `${mode}:${originCount === 1 ? 'single' : 'multi'}`
}

function isDisplayWeights(value: unknown): value is DisplayWeights {
  if (!value || typeof value !== 'object') return false
  const weights = value as DisplayWeights
  const values = [weights.weather, weights.distance, weights.popularity]
  return values.every((item) => Number.isInteger(item) && item >= 0 && item <= 100)
    && values.reduce((sum, item) => sum + item, 0) === 100
}

export function toRankingWeights(
  value: DisplayWeights,
  originCount: 1 | 2 | 3,
): RankingWeights {
  if (originCount === 1) return { ...value, fairness: 0 }
  return {
    weather: value.weather * 0.8,
    distance: value.distance * 0.8,
    fairness: 20,
    popularity: value.popularity * 0.8,
  }
}

export function chinaDate(offsetDays: number) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(Date.now() + offsetDays * 86_400_000))
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${value.year}-${value.month}-${value.day}`
}
