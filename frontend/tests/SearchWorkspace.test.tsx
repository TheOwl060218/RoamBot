import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { apiClient } from '../src/api/client'
import type { RecommendationResponse } from '../src/api/types'
import { AuthProvider } from '../src/features/auth/AuthProvider'
import { SearchWorkspace } from '../src/features/search/SearchWorkspace'

const response: RecommendationResponse = {
  generated_at: '2026-07-17T08:00:00Z',
  source_state: { kind: 'demo', notices: ['苏州内置演示数据'] },
  items: [
    {
      destination: {
        provider_id: 'jinji-lake',
        name: '金鸡湖景区',
        address: '苏州工业园区',
        city: '苏州',
        coordinate: { longitude: 120.7, latitude: 31.3, system: 'gcj02' },
        type_name: '风景名胜',
        type_code: '110000',
        scenery_tags: ['lake', 'park'],
        popularity_rank: 1,
      },
      distances: [
        { origin_label: '主出发地', distance_km: 12.34, duration_minutes: 25, estimated: false },
      ],
      group_accessibility: {
        average_distance_km: 12.34,
        max_distance_km: 12.34,
        distance_variance: 0,
        distance_stddev: 0,
        fairness_score: 100,
      },
      weather: [
        {
          date: '2026-07-18',
          condition: '晴',
          temp_min_c: 23,
          temp_max_c: 31,
          precipitation_mm: 0,
          wind_speed_kmh: 8,
          humidity_percent: 60,
          visibility_km: 20,
          uv_index: 5,
        },
      ],
      daily_suitability: [{ date: '2026-07-18', score: 90, reasons: ['天气晴朗'] }],
      score: {
        weather: 90,
        distance: 75.3,
        fairness: 100,
        popularity: 100,
        coverage_penalty: 0,
        total: 86.59,
      },
      explanation: '天气和距离都适合短途出游。',
    },
  ],
}

describe('SearchWorkspace', () => {
  it('submits the form and displays a complete recommendation result', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    vi.spyOn(apiClient, 'post').mockResolvedValueOnce(response)
    render(<AuthProvider><SearchWorkspace /></AuthProvider>)

    await user.type(screen.getByLabelText('主出发地'), '苏州站')
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))

    expect(await screen.findByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
    expect(screen.getByText('86.6')).toBeInTheDocument()
    expect(screen.getByText('演示数据')).toBeInTheDocument()
    expect(screen.getByText(/12.34 km/)).toBeInTheDocument()
    expect(screen.getByText(/天气晴朗/)).toBeInTheDocument()
    expect(screen.getByText('天气和距离都适合短途出游。')).toBeInTheDocument()
  })
})
