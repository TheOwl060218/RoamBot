import { useEffect, useRef, useState } from 'react'
type Layer = { owner: string; version: number; id: string; map: boolean }
const KEY = 'roambotStudioLayer'
export function useDetailTransition(detailId: string | null, version: number | undefined, onDetail: (id: string | null) => void) {
  const owner = useRef(crypto.randomUUID()), anchor = useRef<HTMLElement | null>(null), scroll = useRef(0)
  const [mapOpen, setMapOpen] = useState(false)
  const previousMap = useRef(false)
  const navigating = useRef(false)
  const latest = useRef({ detailId, version, onDetail })
  useEffect(() => { latest.current = { detailId, version, onDetail } }, [detailId, version, onDetail])
  function marker(): Layer | undefined { return window.history.state?.[KEY] }
  function push(id: string, map: boolean) {
    const layer: Layer = { owner: owner.current, version: version ?? 0, id, map }
    window.history.pushState({ ...window.history.state, [KEY]: layer }, '', window.location.href)
  }
  function open(id: string) {
    if (navigating.current) return
    anchor.current = document.activeElement as HTMLElement; scroll.current = window.scrollY
    push(id, false); onDetail(id)
  }
  function openMap() { if (detailId && !mapOpen && !marker()?.map && !navigating.current) { push(detailId, true); setMapOpen(true) } }
  function back() { if (!navigating.current) { navigating.current = true; window.history.back() } }
  function closeMap() { if (marker()?.owner === owner.current && marker()?.map) back(); else setMapOpen(false) }
  function close() {
    if (marker()?.owner === owner.current) back()
    else onDetail(null)
  }
  useEffect(() => {
    const pop = () => {
      navigating.current = false
      const layer = marker(), s = latest.current
      if (layer?.owner === owner.current && layer.version === s.version) { setMapOpen(layer.map); s.onDetail(layer.id) }
      else { setMapOpen(false); s.onDetail(null) }
    }
    window.addEventListener('popstate', pop)
    return () => window.removeEventListener('popstate', pop)
  }, [])
  useEffect(() => {
    if (!detailId) {
      const frame = requestAnimationFrame(() => {
        if (anchor.current?.isConnected) { window.scrollTo({ top: scroll.current, behavior: 'instant' }); anchor.current.focus({ preventScroll: true }) }
      })
      return () => cancelAnimationFrame(frame)
    }
  }, [detailId])
  useEffect(() => {
    const closed = previousMap.current && !mapOpen
    previousMap.current = mapOpen
    if (closed && detailId) {
      const frame = requestAnimationFrame(() => document.querySelector<HTMLElement>('[data-studio-map-trigger]')?.focus({ preventScroll: true }))
      return () => cancelAnimationFrame(frame)
    }
  }, [mapOpen, detailId])
  useEffect(() => {
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape' && !e.defaultPrevented && detailId && !mapOpen) { e.preventDefault(); close() } }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  })
  // New batches remove owned markers, so Back/Forward cannot revive an obsolete destination.
  useEffect(() => {
    const layer = marker()
    if (layer?.owner === owner.current && layer.version !== version) {
      const state = { ...window.history.state }; delete state[KEY]; window.history.replaceState(state, '', window.location.href)
      const frame = requestAnimationFrame(() => setMapOpen(false))
      return () => cancelAnimationFrame(frame)
    }
  }, [version])
  return { open, close, openMap, closeMap, mapOpen: mapOpen && !!detailId }
}
