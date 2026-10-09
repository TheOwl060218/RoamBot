import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

import { QuerySummary } from '../src/features/search/QuerySummary'
import type { RecommendationRequest } from '../src/api/types'
import type { TravelFormDraft } from '../src/features/search/formState'

vi.mock('../src/features/search/regions', () => ({ loadRegionCatalog: async () => ({
  version: 'test', regions: [{ adcode: '330100', name: '杭州市', level: 'city', province_adcode: '330000' }],
}) }))
it('summary_uses_submitted_request_not_edited_draft', async () => {
  const request: RecommendationRequest = { city: '苏州', main_origin: '已提交出发地',
    companion_origins: [], main_origin_coordinate: null, companion_origin_coordinates: [],
    max_distance_km: 200, start_date: '2026-10-09', end_date: '2026-10-09',
    weights: { weather: 40, distance: 30, popularity: 30, fairness: 0 },
    scenery_types: ['lake'], scenery_match_mode: 'any', destination_regions: ['330100'] }
  render(<QuerySummary draft={null} request={request} onEdit={() => {}} />)
  expect(await screen.findByText(/杭州市/)).toBeInTheDocument()
  expect(screen.getByText(/已提交出发地/)).toBeInTheDocument()
  expect(screen.queryByText('200 km 内')).not.toBeInTheDocument()
})

it('old_result_without_request_does_not_claim_an_edited_region_filter', () => {
  const draft: TravelFormDraft = { mode: 'recommendation', city: '苏州', mainOrigin: '苏州站',
    companions: [], mainOriginCoordinate: null, companionOriginCoordinates: [], maxDistance: '50',
    startDate: '2026-10-09', endDate: '2026-10-09', sceneryTypes: ['lake'], matchMode: 'any',
    targetPlace: '', destinationRegions: ['330100'] }
  render(<QuerySummary draft={draft} onEdit={() => {}} />)
  expect(screen.getByText('旧结果未记录目的地范围')).toBeInTheDocument()
  expect(screen.queryByText(/杭州市|最大距离内不限省市/)).not.toBeInTheDocument()
})
