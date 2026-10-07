import { afterEach, expect, test, vi } from 'vitest'
import type { HistoryDetail, RecommendationRequest } from '../src/api/types'
import { restoreHistorySearch } from '../src/features/history/restoreHistorySearch'
import { loadSearchResult, loadTravelDraft } from '../src/features/search/formState'

const request: RecommendationRequest = {
  city: '杭州', main_origin: '杭州东站', companion_origins: ['西湖'],
  main_origin_coordinate: { longitude: 120, latitude: 30, system: 'gcj02' },
  companion_origin_coordinates: [null], max_distance_km: 35,
  start_date: '2026-12-01', end_date: '2026-12-03',
  scenery_types: ['museum'], scenery_match_mode: 'cover_all',
  weights: { weather: 32, distance: 24, popularity: 24, fairness: 20 },
}
const history: HistoryDetail = { id: 'new-history', mode: 'recommendation', request,
  result: { items: [], source_state: { kind: 'demo', notices: [] }, generated_at: '2026-10-06', uncovered_scenery_types: [] },
  created_at: '2026-10-06', snapshot: true }
afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear() })

test('restores the rerun request rather than stale drafts and excludes fairness from display weights', () => {
  const restored = restoreHistorySearch(history, 'owner')
  expect(restored.draft).toEqual({ mode: 'recommendation', city: '杭州', mainOrigin: '杭州东站',
    companions: ['西湖'], mainOriginCoordinate: request.main_origin_coordinate,
    companionOriginCoordinates: [null], maxDistance: '35', startDate: request.start_date,
    endDate: request.end_date, sceneryTypes: ['museum'], matchMode: 'cover_all', targetPlace: '',
    weights: { weather: 40, distance: 30, popularity: 30 } })
  expect(restored.result).toMatchObject({ history_id: 'new-history', history_owner: 'owner', query_request: request })
  expect(loadTravelDraft()).toEqual(restored.draft)
  expect(loadSearchResult()).toEqual(restored.result)
})

test('keeps evaluation targets and uses default weights for a zero sum', () => {
  const restored = restoreHistorySearch({ ...history, mode: 'place_evaluation',
    request: { ...request, target_place: '西湖', weights: { weather: 0, distance: 0, popularity: 0, fairness: 100 } },
    result: { source_state: { kind: 'demo', notices: [] }, generated_at: '2026-10-06', item: null as never } }, 'owner')
  expect(restored.draft).toMatchObject({ mode: 'place_evaluation', targetPlace: '西湖', weights: { weather: 40, distance: 30, popularity: 30 } })
})

test('returns in-memory data even when session storage is disabled', () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('disabled') })
  expect(restoreHistorySearch(history, 'owner').result.history_id).toBe('new-history')
})

test('rounding display weights never produces a total above 100', () => {
  const restored = restoreHistorySearch({ ...history, request: { ...request,
    weights: { weather: 50.5, distance: 49.5, popularity: 0, fairness: 0 } } }, 'owner')
  const weights = restored.draft.weights!
  expect(weights.weather + weights.distance + weights.popularity).toBe(100)
})
