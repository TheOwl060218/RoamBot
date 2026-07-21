import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { RecommendationItem } from '../src/api/types'
import { ResultCard } from '../src/features/search/ResultCard'

function recommendationItem(originCount: 1 | 2 = 1): RecommendationItem {
  return {
    destination: {
      provider_id: 'jinji-lake',
      name: '金鸡湖景区',
      address: '苏州工业园区',
      city: '苏州',
      coordinate: { longitude: 120.7, latitude: 31.3, system: 'gcj02' },
      type_name: '风景名胜',
      type_code: '110000',
      scenery_tags: ['lake'],
      popularity_rank: 1,
    },
    distances: Array.from({ length: originCount }, (_, index) => ({
      origin_label: index === 0 ? '主出发地' : '同行人 1',
      distance_km: 12.34 + index,
      duration_minutes: 25 + index,
      estimated: false,
    })),
    group_accessibility: {
      average_distance_km: 12.84,
      max_distance_km: 13.34,
      distance_variance: originCount === 1 ? 0 : 0.25,
      distance_stddev: originCount === 1 ? 0 : 0.5,
      fairness_score: originCount === 1 ? 100 : 75,
    },
    weather: [{
      date: '2026-07-23',
      condition: '晴',
      temp_min_c: 23,
      temp_max_c: 31,
      precipitation_mm: 0,
      wind_speed_kmh: 8,
      humidity_percent: 60,
      visibility_km: 20,
      uv_index: 5,
    }],
    daily_suitability: [{ date: '2026-07-23', score: 90, reasons: ['天气晴朗'] }],
    score: {
      weather: 90,
      distance: 75.3,
      fairness: originCount === 1 ? 100 : 75,
      popularity: 88,
      coverage_penalty: 0,
      total: 86.59,
    },
    explanation: '天气和距离都适合短途出游。',
  }
}

describe('ResultCard', () => {
  it('presents an integer trip match index and qualitative dimensions', () => {
    render(<ResultCard item={recommendationItem()} />)

    expect(screen.getByLabelText('出游匹配指数 87')).toBeInTheDocument()
    expect(screen.getByText('非常适合')).toBeInTheDocument()
    expect(screen.getByText('较轻松')).toBeInTheDocument()
    expect(screen.getByText('人气很高')).toBeInTheDocument()
    expect(screen.queryByText('同行均衡')).not.toBeInTheDocument()
    expect(screen.getByText('指数用于比较本次候选地点，不代表官方评价。')).toBeInTheDocument()
    expect(screen.queryByText('90.0')).not.toBeInTheDocument()
    expect(screen.queryByText('75.3')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('分项评分')).not.toBeInTheDocument()
  })

  it('adds a qualitative balance description for group travel', () => {
    render(<ResultCard item={recommendationItem(2)} />)

    expect(screen.getByText('同行均衡')).toBeInTheDocument()
    expect(screen.getByText('比较均衡')).toBeInTheDocument()
    expect(screen.queryByText('75.0')).not.toBeInTheDocument()
  })
})
