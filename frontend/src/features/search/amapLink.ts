export function amapPlaceUrl(providerId: string): string | null {
  const match = /^amap:([A-Za-z0-9]+)$/.exec(providerId)
  if (!match) return null
  return `https://uri.amap.com/poidetail?${new URLSearchParams({ poiid: match[1], src: 'RoamBot', callnative: '1' })}`
}

export function amapSearchUrl(name: string, city: string): string {
  return `https://uri.amap.com/search?${new URLSearchParams({ keyword: name, city, view: 'list', src: 'RoamBot', callnative: '1' })}`
}

type NavigationPoint = { name: string; coordinate: { longitude: number; latitude: number } }
export function amapNavigationUrl(from: NavigationPoint, to: NavigationPoint, mode: 'walking' | 'bicycling' | 'driving'): string | null {
  const point = (value: NavigationPoint) => {
    const { longitude, latitude } = value.coordinate
    if (!Number.isFinite(longitude) || !Number.isFinite(latitude) || Math.abs(longitude) > 180 || Math.abs(latitude) > 90) return null
    return `${longitude.toFixed(6)},${latitude.toFixed(6)},${value.name.replaceAll(',', '，')}`
  }
  const start = point(from), end = point(to)
  if (!start || !end) return null
  return `https://uri.amap.com/navigation?${new URLSearchParams({ from: start, to: end,
    mode: { walking: 'walk', bicycling: 'ride', driving: 'car' }[mode], coordinate: 'gaode', src: 'RoamBot', callnative: '1' })}`
}
