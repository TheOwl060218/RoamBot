import type { DiscoveryCard } from '../discovery/types'

export type Stop = { id: string; place: DiscoveryCard['place']; experience: string; added_at: string }
export type ItineraryDay = { date: string; stop_ids: string[] }
export type ItineraryRoute = { date: string; from_id: string; to_id: string; mode: string; actual: boolean;
  distance_km: number | null; duration_minutes: number | null; path: [number, number][] }
export type Itinerary = { id: string; name: string; version: number; created_at: string; updated_at: string;
  start_date: string | null; end_date: string | null; travel_mode: 'walking' | 'bicycling' | 'driving';
  stops: Stop[]; days: ItineraryDay[]; unassigned_ids: string[]; route_status: 'none' | 'dirty' | 'ready' | 'partial';
  routes: ItineraryRoute[]; weather: Record<string, { regional: boolean; fetched_at: number;
    days: { date: string; condition: string; temp_min_c: number; temp_max_c: number; precipitation_mm: number }[] }>;
  notices: string[]; generating_since?: number; generated_at?: string }
export type Source = { source_job_id?: string; history_id?: string; favorite_id?: string; place_id?: string }
export type Collection = { itineraries: Itinerary[]; current_id: string | null }
export const itineraryEvent = 'roambot:itineraries-changed'
export const announceItinerary = () => window.dispatchEvent(new Event(itineraryEvent))
