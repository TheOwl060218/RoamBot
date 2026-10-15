import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { ExternalLink, X } from 'lucide-react'
import type { RecommendationItem } from '../../api/types'
import { amapPlaceUrl, amapSearchUrl } from './amapLink'
import { useLayerExit } from '../studio/useLayerExit'
import { useModalLayer } from '../studio/useModalLayer'

type Props = {
  items: RecommendationItem[]
  selectedId: string
  onSelect?: (item: RecommendationItem) => void
  onClose: () => void
  children?: ReactNode
}

type Point = [number, number]
type MapInstance = {
  add: (markers: unknown[]) => void
  setFitView: () => void
  setZoomAndCenter: (zoom: number, point: Point) => void
  on: (event: string, callback: () => void) => void
  destroy: () => void
}
type MapSdk = {
  Map: new (element: HTMLElement, options: object) => MapInstance
  Marker: new (options: object) => unknown
}
type MapWindow = Window & {
  AMap?: MapSdk
  _AMapSecurityConfig?: { serviceHost: string }
}
let sdkPromise: Promise<MapSdk> | null = null

async function loadSdk(key: string, serviceHost: string): Promise<MapSdk> {
  const win = window as MapWindow
  if (win.AMap) return win.AMap
  if (!sdkPromise) {
    win._AMapSecurityConfig = { serviceHost: new URL(serviceHost, location.origin).href }
    sdkPromise = new Promise<MapSdk>((resolve, reject) => {
      const script = document.createElement('script')
      script.src = `https://webapi.amap.com/maps?${new URLSearchParams({ v: '2.0', key })}`
      script.async = true
      const timer = window.setTimeout(fail, 12000)
      function fail() {
        clearTimeout(timer)
        script.remove()
        reject(new Error('map_load_failed'))
      }
      script.onerror = fail
      script.onload = () => {
        clearTimeout(timer)
        if (win.AMap) resolve(win.AMap)
        else fail()
      }
      document.head.append(script)
    }).catch(error => { sdkPromise = null; throw error })
  }
  return sdkPromise
}

function point(item: RecommendationItem): Point {
  return [item.destination.coordinate.longitude, item.destination.coordinate.latitude]
}

export function LocationMapDialog({ items, selectedId, onSelect, onClose, children }: Props) {
  const headingId = useId()
  const backdropRef = useRef<HTMLDivElement>(null)
  useLayerExit(backdropRef, '.location-dialog')
  useModalLayer(backdropRef)
  const closeRef = useRef<HTMLButtonElement>(null)
  const canvasRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapInstance | null>(null)
  const selectRef = useRef(onSelect)
  const selectedRef = useRef(selectedId)
  const [attempt, setAttempt] = useState(0)
  const [status, setStatus] = useState('正在加载地图…')
  const [ready, setReady] = useState(false)
  const selected = items.find(item => item.destination.provider_id === selectedId) ?? items[0]
  const markersRef = useRef<{ id: string; element: HTMLElement }[]>([])

  useEffect(() => { selectRef.current = onSelect; selectedRef.current = selectedId }, [onSelect, selectedId])
  useEffect(() => {
    function escape(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape' && !event.defaultPrevented) onClose()
    }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [onClose])
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    closeRef.current?.focus({ preventScroll: true })
    return () => previous?.focus({ preventScroll: true })
  }, [])

  useEffect(() => {
    let cancelled = false
    let timer = 0
    let configTimer = 0
    const controller = new AbortController()
    // All input coordinates are already GCJ-02. Do not request device location.
    async function start() {
      try {
        configTimer = window.setTimeout(() => controller.abort(), 8000)
        const response = await fetch('/api/v1/maps/config', { signal: controller.signal })
        clearTimeout(configTimer)
        if (!response.ok) throw new Error('map_load_failed')
        const config = await response.json()
        if (cancelled) return
        if (!config.enabled) { setStatus('地图暂未配置，请稍后再试'); return }
        const sdk = await loadSdk(config.key, config.service_host)
        if (cancelled || !canvasRef.current) return
        const map = new sdk.Map(canvasRef.current, { zoom: 13, center: point(items[0]), viewMode: '2D' })
        mapRef.current = map
        markersRef.current = []
        const markers = items.filter(item => item.destination.coordinate.system === 'gcj02').map(item => {
          const element = document.createElement('button')
          element.type = 'button'
          element.className = `location-marker${item.destination.provider_id === selectedRef.current ? ' is-selected' : ''}`
          element.textContent = item.destination.name
          element.setAttribute('aria-label', `选择${item.destination.name}`)
          element.onclick = () => selectRef.current?.(item)
          markersRef.current.push({ id: item.destination.provider_id, element })
          return new sdk.Marker({ position: point(item), content: element, anchor: 'bottom-center' })
        })
        timer = window.setTimeout(() => {
          if (!cancelled) setStatus('地图加载失败，可重试或打开高德')
        }, 12000)
        map.on('complete', () => {
          clearTimeout(timer)
          if (!cancelled) { setReady(true); setStatus('') }
        })
        map.add(markers)
        map.setFitView()
      } catch {
        clearTimeout(configTimer)
        if (!cancelled) setStatus('地图加载失败，可重试或打开高德')
      }
    }
    void start()
    return () => {
      cancelled = true
      controller.abort()
      clearTimeout(configTimer)
      clearTimeout(timer)
      mapRef.current?.destroy()
      mapRef.current = null
      markersRef.current = []
    }
  }, [items, attempt])

  useEffect(() => {
    if (!ready || !selected) return
    mapRef.current?.setZoomAndCenter(13, point(selected))
    for (const marker of markersRef.current) {
      marker.element.classList.toggle('is-selected', marker.id === selectedId)
    }
  }, [selected, selectedId, ready])

  function keyboard(event: KeyboardEvent<HTMLElement>) {
    if (event.defaultPrevented) return
    if (event.key === 'Escape') { event.preventDefault(); onClose(); return }
    if (event.key !== 'Tab') return
    const elements = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), [tabindex="0"]')).filter(node => !node.closest('[inert]'))
    const first = elements[0]
    const last = elements.at(-1)
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }

  return createPortal(
    <div ref={backdropRef} className="dialog-backdrop location-backdrop" onKeyDown={keyboard} onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
      <section className="location-dialog" role="dialog" aria-modal="true" aria-labelledby={headingId}>
        <header className="location-heading">
          <div><h2 id={headingId}>景点位置</h2></div>
          <button ref={closeRef} className="text-button" type="button" aria-label="关闭地图" onClick={onClose}><X size={20} /></button>
        </header>
        <div className="location-candidates" aria-label="选择地图景点">
          {items.map(item => <button key={item.destination.provider_id} type="button" className="text-button" aria-pressed={item.destination.provider_id === selectedId} onClick={() => onSelect?.(item)}>{item.destination.name}</button>)}
        </div>
        <div className="location-map-wrap">
          <div className="location-map" ref={canvasRef} aria-label="高德景点位置地图" />
          {status && <div className="location-map-status" role="status"><p>{status}</p>{!status.startsWith('正在') && <button className="text-button" type="button" onClick={() => { setReady(false); setStatus('正在加载地图…'); setAttempt(value => value + 1) }}>重试加载</button>}</div>}
        </div>
        {selected && <footer className="location-footer"><div><strong>{selected.destination.name}</strong><p>{selected.destination.city} · {selected.destination.address}</p></div>
          {amapPlaceUrl(selected.destination.provider_id) && <a className="text-button place-map-link" href={amapSearchUrl(selected.destination.name, selected.destination.city)} target="_blank" rel="noopener noreferrer"><ExternalLink size={16} />打开高德</a>}
        </footer>}
      </section>
      {children}
    </div>, document.body,
  )
}
