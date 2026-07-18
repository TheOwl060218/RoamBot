import type { RankingWeights, SearchMode } from '../../api/types'

const STORAGE_KEY = 'roambot.ui.weights.v1'

export const singleWeights: RankingWeights = {
  weather: 40,
  distance: 30,
  fairness: 0,
  popularity: 30,
}

export const groupWeights: RankingWeights = {
  weather: 40,
  distance: 0,
  fairness: 40,
  popularity: 20,
}

type StoredPreferences = Record<string, RankingWeights>

export function loadWeightPreference(mode: SearchMode, originCount: 1 | 2 | 3) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const stored = JSON.parse(raw) as StoredPreferences
    const value = stored[preferenceKey(mode, originCount)]
    return isRankingWeights(value) ? value : null
  } catch {
    return null
  }
}

export function saveWeightPreference(
  mode: SearchMode,
  originCount: 1 | 2 | 3,
  value: RankingWeights,
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

function isRankingWeights(value: unknown): value is RankingWeights {
  if (!value || typeof value !== 'object') return false
  const weights = value as RankingWeights
  const values = [weights.weather, weights.distance, weights.fairness, weights.popularity]
  return values.every((item) => Number.isInteger(item) && item >= 0 && item <= 100)
    && values.reduce((sum, item) => sum + item, 0) === 100
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
