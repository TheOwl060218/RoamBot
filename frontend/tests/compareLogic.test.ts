import { describe, expect, it } from 'vitest'

import type { RecommendationItem } from '../src/api/types'
import { compareCandidates } from '../src/features/search/compareLogic'

function recommendationItem(
  id: string,
  name: string,
  score: Partial<RecommendationItem['score']>,
  group: Partial<RecommendationItem['group_accessibility']> = {},
  weatherScore?: number,
): RecommendationItem {
  const weather = weatherScore ?? score.weather ?? 0
  return {
    destination: {
      provider_id: id,
      name,
      address: `${name}地址`,
      city: '苏州',
      coordinate: { longitude: 120.7, latitude: 31.3, system: 'gcj02' },
      type_name: '风景名胜',
      type_code: '110000',
      scenery_tags: ['lake'],
      popularity_rank: 1,
      rating: 4.5,
    },
    distances: [
      { origin_label: '主出发地', distance_km: group.average_distance_km ?? 10, duration_minutes: 20, estimated: false },
    ],
    group_accessibility: {
      average_distance_km: group.average_distance_km ?? 10,
      max_distance_km: group.max_distance_km ?? 12,
      distance_variance: group.distance_variance ?? 0,
      distance_stddev: group.distance_stddev ?? 0,
      fairness_score: group.fairness_score ?? 100,
    },
    weather: [{ date: '2026-07-25', condition: '晴', temp_min_c: 20, temp_max_c: 30, precipitation_mm: 0, wind_speed_kmh: 8, humidity_percent: 60, visibility_km: 20, uv_index: 5 }],
    daily_suitability: [{ date: '2026-07-25', score: weather, status: 'suitable', summary: '适合出行', reasons: ['适合'] }],
    score: {
      weather,
      distance: 80,
      fairness: 100,
      popularity: 80,
      coverage_penalty: 0,
      total: 80,
      ...score,
    },
    explanation: `${name}推荐理由`,
    overall_advice: 'suitable',
  }
}

function groupItem(
  id: string,
  name: string,
  score: Partial<RecommendationItem['score']>,
  group: { average_distance_km: number; max_distance_km: number; fairness_score: number },
): RecommendationItem {
  return recommendationItem(id, name, score, { ...group, distance_variance: 0, distance_stddev: 0 }, undefined)
}

describe('compareCandidates', () => {
  it('returns null when fewer than two candidates are compared', () => {
    const single = [recommendationItem('a', 'A', { total: 80, weather: 80 })]
    expect(compareCandidates(single, 1)).toBeNull()
    expect(compareCandidates([], 1)).toBeNull()
  })

  it('builds one value row per candidate across every compared metric', () => {
    const items = [
      recommendationItem('a', 'A', { total: 85, weather: 90 }),
      recommendationItem('b', 'B', { total: 70, weather: 60 }),
    ]
    const result = compareCandidates(items, 1)

    expect(result).not.toBeNull()
    const rows = result!.rows

    const metricKeys = rows.map((row) => row.key)
    expect(metricKeys).toEqual(
      expect.arrayContaining(['total', 'weather', 'avgDistance', 'maxDistance', 'fairness', 'popularity']),
    )

    for (const row of rows) {
      expect(row.values).toHaveLength(2)
      expect(row.values[0].providerId).toBe('a')
      expect(row.values[1].providerId).toBe('b')
    }

    const totalRow = rows.find((row) => row.key === 'total')!
    expect(totalRow.values.map((v) => v.name)).toEqual(['A', 'B'])
    expect(totalRow.bestIds).toEqual(['a'])
  })

  it('supports comparing three candidates', () => {
    const items = [
      recommendationItem('a', 'A', { total: 80 }),
      recommendationItem('b', 'B', { total: 75 }),
      recommendationItem('c', 'C', { total: 70 }),
    ]
    const result = compareCandidates(items, 1)
    expect(result).not.toBeNull()
    for (const row of result!.rows) {
      expect(row.values).toHaveLength(3)
    }
  })

  it('detects a clearly better weather candidate and calls it out', () => {
    const items = [
      recommendationItem('a', 'A', { total: 88, weather: 60 }, undefined, 60),
      recommendationItem('b', 'B', { total: 82, weather: 92 }, undefined, 92),
    ]
    const result = compareCandidates(items, 1)
    const conclusion = result!.conclusions.join(' ')

    expect(conclusion).toContain('B')
    expect(conclusion).toContain('天气')
  })

  it('detects a clearly more balanced candidate for group travel', () => {
    const items = [
      groupItem('a', 'A', { total: 90, weather: 70 }, { average_distance_km: 12, max_distance_km: 30, fairness_score: 40 }),
      groupItem('b', 'B', { total: 85, weather: 75 }, { average_distance_km: 11, max_distance_km: 13, fairness_score: 92 }),
    ]
    const result = compareCandidates(items, 2)
    const conclusion = result!.conclusions.join(' ')

    expect(conclusion).toContain('B')
    expect(conclusion).toContain('同行')
  })

  it('suggests a preference-based decision when totals are close', () => {
    const items = [
      recommendationItem('a', 'A', { total: 83, weather: 80 }),
      recommendationItem('b', 'B', { total: 82, weather: 60 }),
    ]
    const result = compareCandidates(items, 1)
    const conclusion = result!.conclusions.join(' ')

    expect(conclusion).toContain('偏好')
    expect(conclusion).toContain('天气')
  })

  it('names the best overall candidate when it leads clearly', () => {
    const items = [
      recommendationItem('a', 'A', { total: 90, weather: 80 }),
      recommendationItem('b', 'B', { total: 72, weather: 70 }),
    ]
    const result = compareCandidates(items, 1)
    const conclusion = result!.conclusions.join(' ')

    expect(conclusion).toContain('A')
    expect(conclusion).toContain('综合')
  })

  it('is deterministic: same input yields identical output', () => {
    const items = [
      recommendationItem('a', 'A', { total: 85, weather: 88 }),
      recommendationItem('b', 'B', { total: 80, weather: 70 }),
    ]
    const first = compareCandidates(items, 1)
    const second = compareCandidates(items, 1)

    expect(second).toEqual(first)
  })

  it('exposes score composition so weather/distance/fairness/popularity are comparable', () => {
    const items = [
      recommendationItem('a', 'A', { total: 84, weather: 75, distance: 60, fairness: 100, popularity: 55 }),
      recommendationItem('b', 'B', { total: 84, weather: 85, distance: 90, fairness: 100, popularity: 95 }),
    ]
    const result = compareCandidates(items, 1)
    expect(result).not.toBeNull()

    const byMetric: Record<string, number[]> = {}
    for (const row of result!.rows) {
      byMetric[row.key] = row.values.map((v) => v.value)
    }
    expect(byMetric['weather']).toEqual([75, 85])
    expect(byMetric['distance']).toEqual([60, 90])
    expect(byMetric['popularity']).toEqual([55, 95])
  })

  it('keeps unknown popularity as null and ignores it when picking the best', () => {
    const items = [
      recommendationItem('a', 'A', { total: 80, popularity: null }),
      recommendationItem('b', 'B', { total: 85, popularity: 80 }),
    ]
    const result = compareCandidates(items, 1)
    const popularityRow = result!.rows.find((row) => row.key === 'popularity')!
    expect(popularityRow.values.map((v) => v.value)).toEqual([null, 80])
    expect(popularityRow.bestIds).toEqual(['b'])
  })

  it('yields empty bestIds when every candidate has unknown popularity', () => {
    const items = [
      recommendationItem('a', 'A', { total: 80, popularity: null }),
      recommendationItem('b', 'B', { total: 85, popularity: null }),
    ]
    const result = compareCandidates(items, 1)
    const popularityRow = result!.rows.find((row) => row.key === 'popularity')!
    expect(popularityRow.values.map((v) => v.value)).toEqual([null, null])
    expect(popularityRow.bestIds).toEqual([])
  })

  it('uses count-neutral wording when three candidates are close on total', () => {
    const items = [
      recommendationItem('a', 'A', { total: 84, weather: 80 }),
      recommendationItem('b', 'B', { total: 83, weather: 78 }),
      recommendationItem('c', 'C', { total: 82, weather: 76 }),
    ]
    const result = compareCandidates(items, 1)
    const conclusion = result!.conclusions.join(' ')
    expect(conclusion).toContain('候选综合分接近')
    expect(conclusion).not.toContain('两个候选')
  })

  it('always produces at least one conclusion when totals tie exactly', () => {
    const items = [
      recommendationItem('a', 'A', { total: 80, weather: 80 }),
      recommendationItem('b', 'B', { total: 80, weather: 70 }),
    ]
    const result = compareCandidates(items, 1)!
    expect(result.conclusions.length).toBeGreaterThanOrEqual(1)
  })

  it('adds a fallback conclusion when totals differ without a clear lead', () => {
    const items = [
      recommendationItem('a', 'A', { total: 86, weather: 80 }),
      recommendationItem('b', 'B', { total: 80, weather: 78 }),
    ]
    const result = compareCandidates(items, 1)!
    expect(result.conclusions.length).toBeGreaterThanOrEqual(1)
  })
})
