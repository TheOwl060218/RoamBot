import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { LocationMapDialog } from '../src/features/search/LocationMapDialog'
import type { RecommendationItem } from '../src/api/types'

function resultItem(): RecommendationItem {
  return {
    destination: { provider_id: 'first', name: '金鸡湖', city: '苏州', address: '工业园区',
      coordinate: { longitude: 120.7, latitude: 31.3, system: 'gcj02' }, type_name: '湖景',
      type_code: '110000', scenery_tags: ['lake'], rating: 4.8, popularity_rank: 1 },
    distances: [], weather: [], daily_suitability: [],
    group_accessibility: { average_distance_km: 0, max_distance_km: 0, distance_variance: 0,
      distance_stddev: 0, fairness_score: 100 },
    score: { weather: 90, distance: 80, fairness: 100, popularity: 90, coverage_penalty: 0, total: 85 },
    explanation: '', overall_advice: 'suitable',
  }
}

afterEach(() => vi.unstubAllGlobals())

it('reports missing configuration, keeps candidates usable and retries', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: false }) })
  vi.stubGlobal('fetch', fetcher)
  const first = resultItem()
  const second = { ...first, destination: { ...first.destination, provider_id: 'second', name: '另一景点' } }
  const select = vi.fn()
  render(<LocationMapDialog items={[first, second]} selectedId={first.destination.provider_id} onSelect={select} onClose={() => {}} />)
  await expect(screen.findByText('地图暂未配置，请稍后再试')).resolves.toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '另一景点' }))
  expect(select).toHaveBeenCalledWith(second)
  fireEvent.click(screen.getByRole('button', { name: '重试加载' }))
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
  expect(document.querySelector('script[src*="webapi.amap.com"]')).toBeNull()
})
