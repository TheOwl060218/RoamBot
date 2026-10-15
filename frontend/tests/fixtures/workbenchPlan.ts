import type { TravelPlan } from '../../src/api/types'

export function workbenchPlan(): TravelPlan {
  const weather = ['2026-12-30', '2026-12-31', '2027-01-01'].map((date, i) => ({ date, condition: i === 1 ? '小雨' : '多云', temp_min_c: 20 + i, temp_max_c: 26 + i, precipitation_mm: 0, wind_speed_kmh: 10, humidity_percent: 60, visibility_km: 10, uv_index: 3 }))
  return {
    id: 'workbench', name: '苏州跨年出行', city: '苏州', start_date: '2026-12-30', end_date: '2027-01-01', expected_count: 3,
    status: 'voting', ended: false, final_candidate_id: null, created_at: '2026-10-06T00:00:00Z', updated_at: '2026-10-06T00:00:00Z', decided_at: null,
    candidates: ['苏州博物馆', '金鸡湖', '穹窿山'].map((name, i) => ({ id: String(i), latest_weather: null, snapshot: {
      destination: { name, address: '苏州', city: '苏州', scenery_tags: ['museum'], rating: null },
      score: { total: 90 - i * 10, weather: 85, distance: 90, fairness: 95, popularity: null, coverage_penalty: 0 },
      group_accessibility: { average_distance_km: 2 + i, max_distance_km: 3 + i, fairness_score: 95, distance_variance: 1, distance_stddev: 1 },
      weather, daily_suitability: weather.map(day => ({ date: day.date, score: 85, status: 'suitable', summary: '当日出行说明', reasons: [] })),
      overall_advice: 'suitable', explanation: '禁止展示的 AI 推荐理由',
    } })),
    me: { id: 'owner', nickname: '名字较长的同行者', preferred_id: null, acceptable_ids: [] },
    participants: [{ id: 'owner', nickname: '发起者', role: 'owner', voted: false }], summary: null, next_weather_check_at: null, invite_active: false,
  }
}
