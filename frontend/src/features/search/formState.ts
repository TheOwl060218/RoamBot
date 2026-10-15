import type { Coordinate, RankingWeights, SceneryType, SearchMode, RecommendationRequest, PlaceEvaluationRequest } from '../../api/types'

const STORAGE_KEY = 'roambot.ui.display-weights.v2'
const DRAFT_KEY = 'roambot.session.search-draft.v1'
const RESULT_KEY = 'roambot.session.search-result.v1'
const SELECTED_PLACE_KEY = 'roambot.session.selected-place.v1'

export type DisplayWeights = Pick<RankingWeights, 'weather' | 'distance' | 'popularity'>

export const defaultDisplayWeights: DisplayWeights = {
  weather: 40,
  distance: 30,
  popularity: 30,
}

type StoredPreferences = Record<string, DisplayWeights>

export type TravelFormDraft = {
  mode: SearchMode
  city: string
  mainOrigin: string
  companions: string[]
  mainOriginCoordinate: Coordinate | null
  companionOriginCoordinates: (Coordinate | null)[]
  maxDistance: string
  startDate: string
  endDate: string
  sceneryTypes: SceneryType[]
  sceneryQuery?: string
  sceneryKeywords?: string[]
  matchMode: 'any' | 'cover_all'
  targetPlace: string
  weights?: DisplayWeights
  destinationRegions?: string[]
}

export function draftFromRequest(request: RecommendationRequest | PlaceEvaluationRequest): TravelFormDraft {
  const sum = request.weights.weather + request.weights.distance + request.weights.popularity
  const weather = sum > 0 ? Math.round(request.weights.weather / sum * 100) : defaultDisplayWeights.weather
  const distance = sum > 0 ? Math.min(100 - weather, Math.round(request.weights.distance / sum * 100)) : defaultDisplayWeights.distance
  return {
    mode: 'target_place' in request ? 'place_evaluation' : 'recommendation', city: request.city,
    mainOrigin: request.main_origin, companions: request.companion_origins,
    mainOriginCoordinate: request.main_origin_coordinate, companionOriginCoordinates: request.companion_origin_coordinates,
    maxDistance: String(request.max_distance_km), startDate: request.start_date, endDate: request.end_date,
    sceneryTypes: 'scenery_types' in request ? request.scenery_types : [],
    sceneryQuery: 'scenery_query' in request ? request.scenery_query ?? '' : '',
    sceneryKeywords: 'scenery_keywords' in request ? request.scenery_keywords ?? [] : [],
    matchMode: 'scenery_match_mode' in request ? request.scenery_match_mode : 'any',
    targetPlace: 'target_place' in request ? request.target_place : '',
    destinationRegions: 'scenery_types' in request ? request.destination_regions ?? [] : [],
    weights: { weather, distance, popularity: Math.max(0, 100 - weather - distance) },
  }
}

export function loadTravelDraft() {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY)
    return raw ? JSON.parse(raw) as TravelFormDraft : null
  } catch {
    return null
  }
}

export function saveTravelDraft(value: TravelFormDraft) {
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(value))
  } catch {
    // Current-tab continuity is optional when storage is unavailable.
  }
}

export function loadSearchResult<T>() {
  try {
    const raw = sessionStorage.getItem(RESULT_KEY)
    return raw ? JSON.parse(raw) as T : null
  } catch {
    return null
  }
}

export function saveSearchResult(value: unknown) {
  try {
    sessionStorage.setItem(RESULT_KEY, JSON.stringify(value, (key, item) =>
      key === 'assistant_context' || key === 'assistantContext' ? undefined : item))
  } catch {
    // Results can still be used in-memory when storage is unavailable.
  }
}

export function loadSelectedPlaceId() {
  try {
    return sessionStorage.getItem(SELECTED_PLACE_KEY)
  } catch {
    return null
  }
}

export function saveSelectedPlaceId(value: string) {
  try {
    sessionStorage.setItem(SELECTED_PLACE_KEY, value)
  } catch {
    // Selection persistence is optional when storage is unavailable.
  }
}

export function clearSearchSession() {
  sessionStorage.removeItem(DRAFT_KEY)
  sessionStorage.removeItem(RESULT_KEY)
  sessionStorage.removeItem(SELECTED_PLACE_KEY)
}

export function clearSearchResult() {
  sessionStorage.removeItem(RESULT_KEY)
  sessionStorage.removeItem(SELECTED_PLACE_KEY)
}

export const HOME_RESET_REQUEST_EVENT = 'roambot.home-reset-request'

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
