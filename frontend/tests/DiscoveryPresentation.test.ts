import { expect, it } from 'vitest'
import { arrivalCoordinate, discoveryTitle, placeArea, routeLabel } from '../src/features/discovery/discoveryPresentation'
import type { DiscoveryCard } from '../src/features/discovery/types'

it('recovers a short original theme for old results without reusing a previous city or a batch command', () => {
  const turns = [
    { role: 'user', content: '去扬州看运河' },
    { role: 'user', content: '想在南京逛旧街和书店' },
    { role: 'assistant', content: '已找到这些去处。' },
    { role: 'user', content: '这些太集中了，希望保留刚才的活动偏好，看看南京其他片区的选择' },
    { role: 'user', content: '换一批' },
  ]
  const query = '南京适合散步和阅读的历史街区与书店，分散在不同片区，不重复之前的地点'
  expect(discoveryTitle(query, null, turns, '南京市')).toBe('想在南京逛旧街和书店')
  expect(discoveryTitle(query, '南京旧街与阅读', turns, '南京市')).toBe('南京旧街与阅读')
  expect(discoveryTitle('去杭州湖边走走', null, turns, '杭州市')).toBe('去杭州湖边走走')
})

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
