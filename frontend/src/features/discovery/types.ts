import type { Coordinate, DailyWeather } from '../../api/types'

export type DiscoverySource = { id: string; kind: string; title?: string; url?: string; excerpt?: string }
export type DiscoveryCard = {
  place: { id: string; name: string; address: string; city: string; coordinate: Coordinate; map_type: string; map_url: string; facts: Record<string, string> }
  experience: string; reason: string; sources: DiscoverySource[]
  route: { mode?: string; distance_km?: number; duration_minutes?: number; unavailable?: boolean } | null
  weather: DailyWeather[] | { unavailable: true } | null
}
export type DiscoverySnapshot = {
  exploration?: { mode: 'batch' | 'area' | null; remaining: number; seen_count: number; new_count: number; used_reserve: boolean }
  conversation?: { role: string; content: string }[]
  position?: { label: string | null; source: 'device' | 'selected' | 'region'; approximate: boolean; accuracy_m: number | null; captured_at: number | null; use_location?: boolean }
  progress_notes?: string[]
  history_id?: string | null
  search_request?: string | null
  display_title?: string | null
  intent?: 'search' | 'business' | null
  id: string; status: 'running' | 'completed' | 'partial' | 'failed' | 'cancelled'; stage: string
  cards: DiscoveryCard[]; reply: string; request_location: boolean; center_name: string | null
  context: { origin: string | null; region: string | null; max_distance_km: number | null; start_date: string | null; end_date: string | null }
  source: 'live' | 'demo'
}

export type DiscoveryLocationDetails = { source: 'device' | 'selected'; name?: string; accuracy_m?: number; captured_at?: number; replace_origin?: boolean }
