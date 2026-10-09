import { expect, it } from 'vitest'
import { amapPlaceUrl } from '../src/features/search/amapLink'

it('uses real POI ids without exposing credentials', () => {
  const url = new URL(amapPlaceUrl('amap:B01234')!)
  expect(url.hostname).toBe('uri.amap.com')
  expect(url.pathname).toBe('/poidetail')
  expect(url.searchParams.get('poiid')).toBe('B01234')
  expect(url.searchParams.has('key')).toBe(false)
})
it.each(['mock:lake', 'amap:synthetic:123', 'amap:', 'other:B01234'])('does not invent a real place for %s', id => {
  expect(amapPlaceUrl(id)).toBeNull()
})
