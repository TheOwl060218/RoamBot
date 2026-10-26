import type { RecommendationResponse } from '../../src/api/types'
import { chinaDate, saveTravelDraft } from '../../src/features/search/formState'
import { createStudioState } from '../../src/features/studio/studioState'
export const studioResponse: RecommendationResponse = {
  generated_at: '2026-10-10T08:00:00Z', source_state: { kind: 'demo', notices: ['内置演示数据'] }, uncovered_scenery_types: [],
  items: Array.from({ length: 4 }, (_, i) => ({
    destination: { provider_id: `place-${i}`, name: ['金鸡湖景区', '苏州博物馆', '留园', '虎丘'][i], address: '苏州园区', city: '苏州', coordinate: { longitude: 120.7, latitude: 31.3, system: 'gcj02' }, type_name: '风景名胜', type_code: '110000', scenery_tags: ['lake'], popularity_rank: i + 1, rating: i === 3 ? null : 4.8 - i * .1 },
    distances: [{ origin_label: '主出发地', distance_km: 12.34 + i * 8, duration_minutes: 25 + i * 10, estimated: false }],
    group_accessibility: { average_distance_km: 12.34 + i * 8, max_distance_km: 12.34 + i * 8, distance_variance: 0, distance_stddev: 0, fairness_score: 100 },
    weather: [{ date: chinaDate(1), condition: '晴', temp_min_c: 18, temp_max_c: 25, precipitation_mm: 0, wind_speed_kmh: 8, humidity_percent: 60, visibility_km: 20, uv_index: 5 }],
    daily_suitability: [{ date: chinaDate(1), score: 90, status: 'suitable', summary: '天气适合出游', reasons: ['天气晴朗'] }],
    score: { weather: 90, distance: 75 - i * 10, fairness: 100, popularity: 100 - i * 10, coverage_penalty: 0, total: 87 - i * 5 },
    explanation: '天气和距离都适合短途出游。', overall_advice: 'suitable',
  })),
}
export function seedStudioDraft() {
  const draft = { ...createStudioState().draft, mainOrigin: '苏州站', startDate: chinaDate(1), endDate: chinaDate(1), sceneryTypes: ['lake' as const] }
  saveTravelDraft(draft)
  return draft
}
