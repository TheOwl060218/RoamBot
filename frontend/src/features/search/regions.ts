import { apiClient } from '../../api/client'

export type Region = {
  adcode: string
  name: string
  level: 'province' | 'city'
  province_adcode: string
}
export type RegionCatalog = { version: string; data_date: string; regions: Region[] }

let pending: Promise<RegionCatalog> | undefined
export function loadRegionCatalog() {
  pending ??= apiClient.get<RegionCatalog>('/regions').catch((error: unknown) => {
    pending = undefined
    throw error
  })
  return pending
}

export function normalizeRegions(values: string[], catalog: RegionCatalog) {
  const selected = new Set(values)
  return [...selected].filter((code) => {
    const row = catalog.regions.find((region) => region.adcode === code)
    return !row || row.level === 'province' || !selected.has(row.province_adcode)
  }).sort()
}
