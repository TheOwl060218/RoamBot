import type { Coordinate, PlaceEvaluationRequest, RecommendationItem, RecommendationRequest, SourceState } from '../../api/types'
import type { TravelFormDraft } from '../search/formState'
const scenery = ['lake','sea','old_town','museum','park','mountain']
const object = (value: unknown) => !!value && typeof value === 'object'
const strings = (value: unknown, limit: number) => Array.isArray(value) && value.length <= limit && value.every(s => typeof s === 'string')
const finite = (value: unknown) => typeof value === 'number' && Number.isFinite(value)
const day = (value: unknown) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value))
const coordinate = (value: unknown) => value === null || object(value) && finite((value as Coordinate).longitude) && finite((value as Coordinate).latitude) && typeof (value as Coordinate).system === 'string'
export function isStoredRequest(value: unknown): value is RecommendationRequest | PlaceEvaluationRequest {
  if (!object(value)) return false
  const r = value as RecommendationRequest | PlaceEvaluationRequest
  return typeof r.city === 'string' && typeof r.main_origin === 'string'
    && strings(r.companion_origins, 2) && day(r.start_date) && day(r.end_date)
    && finite(r.max_distance_km) && r.max_distance_km > 0 && r.max_distance_km <= 500
    && coordinate(r.main_origin_coordinate) && Array.isArray(r.companion_origin_coordinates)
    && r.companion_origin_coordinates.length <= 2 && r.companion_origin_coordinates.every(coordinate)
    && !!r.weights && [r.weights.weather,r.weights.distance,r.weights.fairness,r.weights.popularity].every(finite)
    && ('target_place' in r ? typeof r.target_place === 'string' : strings(r.scenery_types, 6)
      && r.scenery_types.every(t => scenery.includes(t)) && ['any','cover_all'].includes(r.scenery_match_mode)
      && (r.destination_regions === undefined || strings(r.destination_regions, 50)))
}
export function isStoredDraft(value: unknown): value is TravelFormDraft {
  if (!object(value)) return false
  const d = value as TravelFormDraft
  return ['recommendation','place_evaluation'].includes(d.mode) && ['any','cover_all'].includes(d.matchMode)
    && [d.city,d.mainOrigin,d.maxDistance,d.startDate,d.endDate,d.targetPlace].every(v => typeof v === 'string')
    && strings(d.companions, 2) && Array.isArray(d.companionOriginCoordinates)
    && strings(d.sceneryTypes, 6) && d.sceneryTypes.every(v => scenery.includes(v))
    && (d.sceneryQuery === undefined || typeof d.sceneryQuery === 'string' && d.sceneryQuery.length <= 120)
    && (d.sceneryKeywords === undefined || strings(d.sceneryKeywords, 4) && d.sceneryKeywords.every(v => v.length <= 24))
    && (d.destinationRegions === undefined || strings(d.destinationRegions, 50))
    && (d.weights === undefined || !!d.weights && [d.weights.weather,d.weights.distance,d.weights.popularity].every(finite))
}
export function isStoredSource(value: unknown): value is SourceState {
  const s = value as SourceState | null
  return !!s && ['live','cache','demo','degraded'].includes(s.kind) && strings(s.notices, 30)
}
export function isStoredItem(value: unknown): value is RecommendationItem {
  if (!object(value)) return false
  const i = value as RecommendationItem, d = i.destination
  return !!d && [d.provider_id,d.name,d.address,d.city,d.type_name,d.type_code].every(v => typeof v === 'string')
    && !!d.coordinate && [d.coordinate.longitude,d.coordinate.latitude].every(finite) && typeof d.coordinate.system === 'string'
    && strings(d.scenery_tags, 6) && d.scenery_tags.every(t => scenery.includes(t)) && (d.rating === null || finite(d.rating))
    && !!i.score && [i.score.total,i.score.weather,i.score.distance,i.score.fairness].every(finite)
    && (i.score.popularity === null || finite(i.score.popularity))
    && !!i.group_accessibility && [i.group_accessibility.average_distance_km,i.group_accessibility.max_distance_km,i.group_accessibility.fairness_score].every(finite)
    && Array.isArray(i.distances) && i.distances.length <= 3 && i.distances.every(v => !!v && typeof v.origin_label === 'string' && finite(v.distance_km) && (v.duration_minutes === null || finite(v.duration_minutes)))
    && Array.isArray(i.weather) && i.weather.length <= 7 && i.weather.every(w => !!w && day(w.date) && typeof w.condition === 'string' && [w.temp_min_c,w.temp_max_c].every(finite))
    && Array.isArray(i.daily_suitability) && i.daily_suitability.length <= 7 && i.daily_suitability.every(s => !!s && day(s.date) && ['suitable','caution','not_recommended'].includes(s.status) && typeof s.summary === 'string')
    && typeof i.explanation === 'string' && ['suitable','some_dates_caution','some_dates_not_recommended'].includes(i.overall_advice)
}
