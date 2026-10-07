import type { HistoryDetail } from '../../api/types'
import type { SearchResult } from '../search/SearchWorkspace'
import {
  defaultDisplayWeights, saveSearchResult, saveSelectedPlaceId, saveTravelDraft,
  type TravelFormDraft,
} from '../search/formState'

export type RestoredHistorySearch = { result: SearchResult; draft: TravelFormDraft }

export function restoreHistorySearch(history: HistoryDetail, username: string | null): RestoredHistorySearch {
  const request = history.request
  const sum = request.weights.weather + request.weights.distance + request.weights.popularity
  const weather = sum > 0 ? Math.round(request.weights.weather / sum * 100) : defaultDisplayWeights.weather
  const distance = sum > 0 ? Math.min(100 - weather, Math.round(request.weights.distance / sum * 100)) : defaultDisplayWeights.distance
  const weights = { weather, distance, popularity: Math.max(0, 100 - weather - distance) }
  const draft: TravelFormDraft = {
    mode: history.mode, city: request.city, mainOrigin: request.main_origin,
    companions: request.companion_origins, mainOriginCoordinate: request.main_origin_coordinate,
    companionOriginCoordinates: request.companion_origin_coordinates,
    maxDistance: String(request.max_distance_km), startDate: request.start_date, endDate: request.end_date,
    sceneryTypes: 'scenery_types' in request ? request.scenery_types : [],
    matchMode: 'scenery_match_mode' in request ? request.scenery_match_mode : 'any',
    targetPlace: 'target_place' in request ? request.target_place : '', weights,
  }
  const result: SearchResult = { ...history.result, query_request: request,
    history_id: history.id, history_owner: username }
  saveTravelDraft(draft)
  saveSearchResult(result)
  const items = 'items' in result ? result.items : [result.item]
  saveSelectedPlaceId(items[0]?.destination.provider_id ?? '')
  return { result, draft }
}
