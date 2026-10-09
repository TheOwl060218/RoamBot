export function amapPlaceUrl(providerId: string): string | null {
  const match = /^amap:([A-Za-z0-9]+)$/.exec(providerId)
  if (!match) return null
  return `https://uri.amap.com/marker?${new URLSearchParams({ poiid: match[1], src: 'RoamBot', callnative: '1' })}`
}
