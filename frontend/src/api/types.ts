import type { DiscoveryHistory, DiscoveryPlanSnapshot, PublicDiscoverySnapshot } from '../features/discovery/snapshotTypes'

export type SceneryType = 'lake' | 'sea' | 'old_town' | 'museum' | 'park' | 'mountain'
export type SearchMode = 'recommendation' | 'place_evaluation'
export type SourceKind = 'live' | 'cache' | 'demo' | 'degraded'
export type TravelAdviceStatus = 'suitable' | 'caution' | 'not_recommended'
export type OverallAdviceStatus =
  | 'suitable'
  | 'some_dates_caution'
  | 'some_dates_not_recommended'

export type RankingWeights = {
  weather: number
  distance: number
  fairness: number
  popularity: number
}

export type Coordinate = {
  longitude: number
  latitude: number
  system: string
}

export type TravelRequestBase = {
  city: string
  main_origin: string
  companion_origins: string[]
  main_origin_coordinate: Coordinate | null
  companion_origin_coordinates: (Coordinate | null)[]
  max_distance_km: number
  start_date: string
  end_date: string
  weights: RankingWeights
}

export type RecommendationRequest = TravelRequestBase & {
  scenery_query?: string | null
  scenery_keywords?: string[]
  destination_regions?: string[]
  scenery_types: SceneryType[]
  scenery_match_mode: 'any' | 'cover_all'
}

export type PlaceEvaluationRequest = TravelRequestBase & {
  target_place: string
}

export type Destination = {
  provider_id: string
  name: string
  address: string
  city: string
  coordinate: Coordinate
  type_name: string
  type_code: string
  scenery_tags: SceneryType[]
  popularity_rank: number
  rating: number | null
}

export type DailyWeather = {
  date: string
  condition: string
  temp_min_c: number
  temp_max_c: number
  precipitation_mm: number
  wind_speed_kmh: number
  humidity_percent: number
  visibility_km: number
  uv_index: number
}

export type DailySuitability = {
  date: string
  score: number
  status: TravelAdviceStatus
  summary: string
  reasons: string[]
}

export type DistanceEstimate = {
  origin_label: string
  distance_km: number
  duration_minutes: number | null
  estimated: boolean
}

export type ScoreBreakdown = {
  weather: number
  distance: number
  fairness: number
  popularity: number | null
  coverage_penalty: number
  total: number
}

export type RecommendationItem = {
  destination: Destination
  distances: DistanceEstimate[]
  group_accessibility: {
    average_distance_km: number
    max_distance_km: number
    distance_variance: number
    distance_stddev: number
    fairness_score: number
  }
  weather: DailyWeather[]
  daily_suitability: DailySuitability[]
  score: ScoreBreakdown
  explanation: string
  overall_advice: OverallAdviceStatus
}

export type SourceState = { kind: SourceKind; notices: string[] }

export type RecommendationResponse = {
  assistant_context?: string | null
  history_id?: string | null
  items: RecommendationItem[]
  source_state: SourceState
  generated_at: string
  uncovered_scenery_types: SceneryType[]
}

export type PlaceEvaluationResponse = {
  assistant_context?: string | null
  item: RecommendationItem
  source_state: SourceState
  generated_at: string
}

export type AuthResponse = {
  user: { username: string }
  csrf_token: string
}

export type ErrorField = { path: string; message: string }
export type ErrorEnvelope = {
  error: { code: string; message: string; fields: ErrorField[] }
}

export type Favorite = {
  id: string
  place: {
    provider: string
    provider_place_id: string
    name: string
    address: string
    city: string
    coordinate: Coordinate
    type_name: string
    type_code: string
    scenery_tags: SceneryType[]
  }
  created_at: string
}

export type PlaceSuggestion = {
  provider_id: string
  name: string
  district: string
  address: string
  coordinate: Coordinate | null
}

export type HistorySummary = {
  id: string
  mode: SearchMode | 'discovery'
  city: string
  start_date: string | null
  end_date: string | null
  item_count: number
  generated_at: string
  created_at: string
}

export type LegacyHistoryDetail = {
  id: string
  mode: SearchMode
  request: RecommendationRequest | PlaceEvaluationRequest
  result: RecommendationResponse | PlaceEvaluationResponse
  created_at: string
  snapshot: true
}
export type HistoryDetail = LegacyHistoryDetail | DiscoveryHistory

export type Share = {
  id: string
  history_id: string
  url: string
  created_at: string
}

export type PublicItem = {
  destination: Pick<Destination, 'name' | 'address' | 'city' | 'scenery_tags' | 'rating'>
  weather: DailyWeather[]
  daily_suitability: DailySuitability[]
  score: ScoreBreakdown
  explanation: string
  overall_advice: OverallAdviceStatus
}

export type LegacyPublicSnapshot = {
  mode: SearchMode
  city: string
  companion_count: number
  start_date: string
  end_date: string
  items: PublicItem[]
  generated_at: string
  uncovered_scenery_types: SceneryType[]
}
export type PublicSnapshot = LegacyPublicSnapshot | PublicDiscoverySnapshot

export type PlanCandidate = {
  id: string
  snapshot: (PublicItem & { group_accessibility: RecommendationItem['group_accessibility']; source_state?: SourceState | null }) | DiscoveryPlanSnapshot
  latest_weather: {
    checked_at: string
    status: 'success' | 'failed'
    source: string
    risk: 'stable' | 'caution' | 'high' | null
    change: 'stable' | 'attention' | 'worsened' | 'improved' | 'unavailable'
    weather: DailyWeather[] | null
    daily_suitability?: DailySuitability[]
    last_success_at: string | null
  } | null
}

export type TravelPlan = {
  id: string
  name: string
  city: string
  start_date: string
  end_date: string
  expected_count: number
  status: 'voting' | 'closed' | 'decided'
  final_candidate_id: string | null
  ended: boolean
  created_at: string
  updated_at: string
  decided_at: string | null
  candidates: PlanCandidate[]
  participants: { id: string; nickname: string; role: 'owner' | 'guest'; voted: boolean }[] | null
  summary: {
    voted_count: number
    joined_count: number
    complete: boolean
    candidates: { id: string; preferred_count: number; acceptable_count: number; all_accept: boolean }[]
  } | null
  me: { id: string; nickname: string; preferred_id: string | null; acceptable_ids: string[] } | null
  next_weather_check_at: string | null
  invite_active?: boolean
}
