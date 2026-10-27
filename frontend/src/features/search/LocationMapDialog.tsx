import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { ExternalLink, MapPin, X } from 'lucide-react'
import type { Destination } from '../../api/types'
import { amapPlaceUrl, amapSearchUrl } from './amapLink'
import { useLayerExit } from '../studio/useLayerExit'
import { useModalLayer } from '../studio/useModalLayer'
import { useCommandTarget } from '../commands/commandContext'

type MapItem = { destination: Pick<Destination, 'provider_id' | 'name' | 'city' | 'address' | 'coordinate'> }
type Props<T extends MapItem> = {
  items: T[]
  selectedId: string
  onSelect?: (item: T) => void
  onClose: () => void
  children?: ReactNode
  title?: string
  lines?: { path: Point[]; actual: boolean }[]
  numbered?: boolean
  routeControls?: ReactNode
  renderSelected?: (item: T) => ReactNode
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
  Polyline?: new (options: object) => unknown
  TileLayer?: new (options: object) => unknown
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

function point(item: MapItem): Point {
  return [item.destination.coordinate.longitude, item.destination.coordinate.latitude]
}

export function LocationMapDialog<T extends MapItem>({ items, selectedId, onSelect, onClose, children, title = '景点位置', lines, numbered = false, routeControls, renderSelected }: Props<T>) {
  const headingId = useId()
  const backdropRef = useRef<HTMLDivElement>(null)
  useLayerExit(backdropRef, '.location-dialog')
  useModalLayer(backdropRef)
  const closeRef = useRef<HTMLButtonElement>(null)
  const canvasRef = useRef<HTMLDivElement>(null)
  const candidatesRef = useRef<HTMLDivElement>(null)
  const selectedCardRef = useRef<HTMLDivElement>(null)
  const labelRef = useRef<HTMLDivElement>(null)
  const labelUpdateRef = useRef<() => void>(() => {})
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [keyboardId, setKeyboardId] = useState<string | null>(null)
  const mapRef = useRef<MapInstance | null>(null)
  const selectRef = useRef(onSelect)
  const selectedRef = useRef(selectedId)
  const lastFocused = useRef(selectedId)
  const [attempt, setAttempt] = useState(0)
  const [status, setStatus] = useState('正在加载地图…')
  const [ready, setReady] = useState(false)
  const selected = items.find(item => item.destination.provider_id === selectedId) ?? items[0]
  const labelItem = items.find(item => item.destination.provider_id === (hoveredId ?? keyboardId ?? selectedId)) ?? selected
  const markersRef = useRef<{ id: string; element: HTMLElement }[]>([])
  const view = useRef({ zoom: 13, center: point(selected) })
  useCommandTarget('map-view', () => ({ layer: 'map' }), effect => {
    if (effect.tool !== 'control_map') return false
    const action = String(effect.arguments.action)
    if (action === 'retry') { setReady(false); setAttempt(value => value + 1); return true }
    const map = mapRef.current
    if (!map || !ready) throw new Error('地图还未加载完成，可说“重试地图”。')
    if (action === 'reset') { map.setFitView(); view.current = { zoom: 13, center: point(selected) }; return true }
    const next = { ...view.current, center: [...view.current.center] as Point }
    if (action === 'zoom_in') next.zoom = Math.min(20, next.zoom + 1)
    else if (action === 'zoom_out') next.zoom = Math.max(3, next.zoom - 1)
    else {
      const offset = 360 / 2 ** next.zoom * .5
      next.center[0] = Math.max(-180, Math.min(180, next.center[0] + (action === 'left' ? -offset : action === 'right' ? offset : 0)))
      next.center[1] = Math.max(-85, Math.min(85, next.center[1] + (action === 'up' ? offset : action === 'down' ? -offset : 0)))
    }
    view.current = next
    map.setZoomAndCenter(next.zoom, next.center)
    return true
  })

  useEffect(() => { selectRef.current = onSelect; selectedRef.current = selectedId }, [onSelect, selectedId])
  useEffect(() => { if (selectedCardRef.current) selectedCardRef.current.scrollTop = 0 }, [selectedId])
  useEffect(() => {
    const strip = candidatesRef.current
    const button = strip?.querySelector<HTMLElement>('[aria-pressed="true"]')
    if (!strip || !button) return
    const bounds = strip.getBoundingClientRect(), target = button.getBoundingClientRect()
    if (target.left < bounds.left || target.right > bounds.right) {
      const delta = target.width > bounds.width || target.left < bounds.left ? target.left - bounds.left : target.right - bounds.right
      strip.scrollTo?.({ left: strip.scrollLeft + delta, behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
    }
  }, [selectedId])
  useLayoutEffect(() => {
    // Position the name inside the canvas instead of letting marker content
    // change the pin anchor or get clipped at a map edge.
    function positionLabel() {
      const label = labelRef.current, canvas = canvasRef.current
      const marker = markersRef.current.find(marker => marker.id === labelItem?.destination.provider_id)?.element
      if (!label || !canvas || !marker || !ready) return
      const bounds = canvas.getBoundingClientRect(), pin = marker.getBoundingClientRect()
      const x = pin.left + pin.width / 2 - bounds.left, top = pin.top - bounds.top
      label.hidden = x < 0 || x > bounds.width || top + pin.height < 0 || top > bounds.height
      const width = label.offsetWidth, height = label.offsetHeight
      label.style.left = `${Math.max(8, Math.min(bounds.width - width - 8, x - width / 2))}px`
      label.style.top = `${Math.max(8, Math.min(bounds.height - height - 8, top >= height + 12 ? top - height - 8 : top + pin.height + 8))}px`
    }
    labelUpdateRef.current = positionLabel
    positionLabel()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(positionLabel)
    if (canvasRef.current) observer?.observe(canvasRef.current)
    return () => { observer?.disconnect(); labelUpdateRef.current = () => {} }
  }, [labelItem, ready])
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
        const map = new sdk.Map(canvasRef.current, { zoom: 13, center: point(items[0]), viewMode: '2D',
          mapStyle: 'amap://styles/normal', showIndoorMap: false,
          ...(sdk.TileLayer ? { layers: [new sdk.TileLayer({ opacity: .68 })] } : {}) })
        mapRef.current = map
        lastFocused.current = selectedRef.current
        markersRef.current = []
        const markers = items.flatMap((item, index) => {
          if (item.destination.coordinate.system !== 'gcj02') return []
          const element = document.createElement('button')
          element.type = 'button'
          element.className = `location-marker${item.destination.provider_id === selectedRef.current ? ' is-selected' : ''}`
          const head = document.createElement('span')
          head.className = 'location-marker-head'
          head.textContent = String(index+1)
          head.setAttribute('aria-hidden', 'true')
          element.append(head)
          element.setAttribute('aria-label', `选择${item.destination.name}`)
          element.setAttribute('aria-pressed', String(item.destination.provider_id === selectedRef.current))
          element.onmouseenter = () => setHoveredId(item.destination.provider_id)
          element.onmouseleave = () => setHoveredId(null)
          element.onfocus = () => setKeyboardId(item.destination.provider_id)
          element.onblur = () => setKeyboardId(null)
          element.onclick = () => selectRef.current?.(item)
          markersRef.current.push({ id: item.destination.provider_id, element })
          return [new sdk.Marker({ position: point(item), content: element, anchor: 'bottom-center' })]
        })
        timer = window.setTimeout(() => {
          if (!cancelled) setStatus('地图加载失败，可重试或打开高德')
        }, 12000)
        map.on('complete', () => {
          clearTimeout(timer)
          if (!cancelled) { setReady(true); setStatus('') }
        })
        for (const event of ['mapmove', 'zoomchange', 'resize']) map.on(event, () => { if (!cancelled) labelUpdateRef.current() })
        map.add(markers)
        if (sdk.Polyline && lines?.length) {
          map.add(lines.filter(line => line.path.length >= 2).map(line => new sdk.Polyline!({
            path: line.path, strokeColor: line.actual ? '#087e96' : '#7b9ca5', strokeWeight: line.actual ? 6 : 3,
            strokeStyle: line.actual ? 'solid' : 'dashed', showDir: line.actual,
            isOutline: line.actual, outlineColor: '#ffffff', borderWeight: 2,
            strokeOpacity: 1, lineJoin: 'round', lineCap: 'round',
          })))
        }
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
  }, [items, attempt, lines, numbered])

  useEffect(() => {
    if (!ready || !selected) return
    if (items.length === 1 || lastFocused.current !== selectedId) {
      mapRef.current?.setZoomAndCenter(13, point(selected))
      view.current = { zoom: 13, center: point(selected) }
    }
    lastFocused.current = selectedId
    for (const marker of markersRef.current) {
      marker.element.classList.toggle('is-selected', marker.id === selectedId)
      marker.element.setAttribute('aria-pressed', String(marker.id === selectedId))
    }
  }, [selected, selectedId, ready, items.length])

  function keyboard(event: KeyboardEvent<HTMLElement>) {
    if (event.defaultPrevented) return
    if (event.key === 'Escape') { event.preventDefault(); onClose(); return }
    if (event.key !== 'Tab') return
    const elements = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]')).filter(node => !node.closest('[inert], [hidden]'))
    const first = elements[0]
    const last = elements.at(-1)
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }

  return createPortal(
    <div ref={backdropRef} className="dialog-backdrop location-backdrop" onKeyDown={keyboard} onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
      <section className={`location-dialog${renderSelected ? ' location-dialog-with-card' : ''}`} role="dialog" aria-modal="true" aria-labelledby={headingId}>
        <header className="location-heading">
          <div><h2 id={headingId}>{title}</h2>{lines?.length && !routeControls ? <p className='muted'>实线为实际道路，虚线为地点顺序示意</p> : null}</div>
          <button ref={closeRef} className="text-button" type="button" aria-label="关闭地图" onClick={onClose}><X size={20} /></button>
        </header>
        <div ref={candidatesRef} className="location-candidates" aria-label="选择地图景点">
          {items.map((item, index) => <button key={item.destination.provider_id} type="button" className="text-button" aria-pressed={item.destination.provider_id === selectedId} onClick={() => onSelect?.(item)}>{items.length > 1 || numbered ? `${index+1} · ` : ''}{item.destination.name}</button>)}
        </div>
        {items.length > 1 && <div className="location-overview-controls"><span>{items.length} 个{numbered ? '行程' : '推荐'}地点</span>
          <button type="button" className="text-button" disabled={!ready} onClick={() => mapRef.current?.setFitView()}>查看全部地点</button></div>}
        {routeControls}
        <div className='location-content'>
        <div className="location-map-wrap">
          <div className="location-map" ref={canvasRef} aria-label="高德景点位置地图" />
          {ready && labelItem && <div ref={labelRef} className='location-marker-name' aria-hidden='true'>{labelItem.destination.name}</div>}
          {status && <div className="location-map-status"><div className='location-map-status-pill' role="status"><MapPin size={14} aria-hidden='true' /><p>{status}</p>{!status.startsWith('正在') && <button className="text-button" type="button" onClick={() => { setReady(false); setStatus('正在加载地图…'); setAttempt(value => value + 1) }}>重试加载</button>}</div></div>}
        </div>
        {selected && renderSelected && <div ref={selectedCardRef} className='location-selected-card'>{renderSelected(selected)}</div>}
        </div>
        {selected && !renderSelected && <footer className="location-footer"><div><strong>{selected.destination.name}</strong><p>{selected.destination.city} · {selected.destination.address}</p></div>
          {amapPlaceUrl(selected.destination.provider_id) && <a className="text-button place-map-link" href={amapSearchUrl(selected.destination.name, selected.destination.city)} target="_blank" rel="noopener noreferrer"><ExternalLink size={16} />打开高德</a>}
        </footer>}
      </section>
      {children}
    </div>, document.body,
  )
}
