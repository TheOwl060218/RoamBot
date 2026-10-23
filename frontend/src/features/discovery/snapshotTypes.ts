import type { DailyWeather } from '../../api/types'
import type { DiscoveryCard, DiscoverySource, DiscoverySnapshot } from './types'

export type DiscoveryHistory = {
  id: string; mode: 'discovery'; created_at: string; snapshot: true
  request: { message: string; context: DiscoverySnapshot['context'] }
  result: { schema_version: 'discovery-v1'; cards: DiscoveryCard[]; source: 'live' | 'demo'; generated_at: string; status: 'completed' | 'partial' }
}
type PublicPlace = Pick<DiscoveryCard['place'], 'name' | 'address' | 'city' | 'map_type'>
export type PublicDiscoveryCard = { place: PublicPlace; experience: string; reason: string; sources: DiscoverySource[]; weather: DailyWeather[] | null }
export type PublicDiscoverySnapshot = {
  schema_version: 'discovery-v1'; mode: 'discovery'; city: string
  start_date: string | null; end_date: string | null; generated_at: string; cards: PublicDiscoveryCard[]
}
export type DiscoveryPlanSnapshot = {
  schema_version: 'discovery-v1'; destination: PublicPlace; experience: string; reason: string
  sources: DiscoverySource[]; weather: DailyWeather[]; source: 'live' | 'demo'
}
