export function amapPlaceUrl(providerId: string): string | null {
  const match = /^amap:([A-Za-z0-9]+)$/.exec(providerId)
  if (!match) return null
  return `https://uri.amap.com/poidetail?${new URLSearchParams({ poiid: match[1], src: 'RoamBot', callnative: '1' })}`
}

export function amapSearchUrl(name: string, city: string): string {
  return `https://uri.amap.com/search?${new URLSearchParams({ keyword: name, city, view: 'list', src: 'RoamBot', callnative: '1' })}`
}
