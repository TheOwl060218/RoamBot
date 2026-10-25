import { expect, it } from 'vitest'
import { arrivalCoordinate, placeArea, routeLabel } from '../src/features/discovery/discoveryPresentation'
import type { DiscoveryCard } from '../src/features/discovery/types'

const card = { place: { city: '苏州市', coordinate: { longitude: 120.6, latitude: 31.3, system: 'gcj02' },
  facts: { district: '吴中区', entr_location: '120.61,31.31' } },
  route: { mode: 'walking', distance_km: 2.345, duration_minutes: 30 } } as DiscoveryCard

it('uses the map district and entrance and describes the actual route without excess precision', () => {
  expect(placeArea(card)).toBe('苏州市 · 吴中区')
  expect(arrivalCoordinate(card)).toEqual({ longitude: 120.61, latitude: 31.31, system: 'gcj02' })
  expect(routeLabel(card)).toBe('步行 2.3 公里 · 约30分钟 · 至地图入口')
})

it('does not invent missing district or arrival point', () => {
  const missing = { ...card, place: { ...card.place, facts: { entr_location: 'invalid' } }, route: null }
  expect(placeArea(missing)).toBe('苏州市')
  expect(arrivalCoordinate(missing)).toEqual(card.place.coordinate)
  expect(routeLabel(missing)).toBe('')
})
