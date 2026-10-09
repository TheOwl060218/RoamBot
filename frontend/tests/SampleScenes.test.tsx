import { render, screen, fireEvent } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { SampleScenes } from '../src/features/search/SampleScenes'
import { saveTravelDraft } from '../src/features/search/formState'

it('uses current travel conditions when choosing an indoor preset', () => {
  saveTravelDraft({ mode: 'recommendation', city: '福州', mainOrigin: '福州站',
    companions: ['福州南站'], mainOriginCoordinate: null, companionOriginCoordinates: [null],
    maxDistance: '50', startDate: '2026-10-10', endDate: '2026-10-11',
    sceneryTypes: ['sea'], matchMode: 'cover_all', targetPlace: '', destinationRegions: ['310000'] })
  const explore = vi.fn()
  render(<SampleScenes onExplore={explore} />)
  fireEvent.click(screen.getByRole('button', { name: '室内参观' }))
  expect(explore).toHaveBeenCalledWith(expect.objectContaining({ city: '', main_origin: '福州站',
    companion_origins: ['福州南站'], start_date: '2026-10-10', end_date: '2026-10-11',
    destination_regions: ['310000'], scenery_types: ['museum'], max_distance_km: 50, scenery_match_mode: 'cover_all' }))
})

it.each([
  ['短途近程', 'park', 30], ['室内参观', 'museum', 40],
  ['临湖', 'lake', 60], ['人文古迹', 'old_town', 60],
])('preset %s starts its own scenery search', (label, type, distance) => {
  const explore = vi.fn()
  render(<SampleScenes onExplore={explore} />)
  fireEvent.click(screen.getByRole('button', { name: String(label) }))
  expect(explore).toHaveBeenCalledWith(expect.objectContaining({
    scenery_types: [type], max_distance_km: distance,
  }))
})
