import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowDown, ArrowUp, Bike, CarFront, ExternalLink, Footprints, GripVertical, Map as MapIcon, Plus, X } from 'lucide-react'
import { apiClient } from '../../api/client'
import { useAuth } from '../auth/authContext'
import { useBusinessAssistant, useCommandTarget } from '../commands/commandContext'
import { BUSINESS_CHANGED } from '../commands/commandEvents'
import { OverlayHost } from '../studio/OverlayHost'
import { LocationMapDialog } from '../search/LocationMapDialog'
import { amapNavigationUrl } from '../search/amapLink'
import { arrivalCoordinate, placeType } from '../discovery/discoveryPresentation'
import type { DiscoveryCard } from '../discovery/types'
import { announceItinerary, itineraryEvent, type Collection, type Itinerary, type ItineraryDay, type Stop } from './types'
import '../../styles/itineraries.css'

type Envelope = { itinerary: Itinerary }
const modeNames = { walking: '步行', bicycling: '骑行', driving: '驾车' }
const modeIcons = { walking: Footprints, bicycling: Bike, driving: CarFront }
const lastDate = (start: string) => start && Number.isFinite(Date.parse(start)) ? new Date(Date.parse(start) + 29*86400000).toISOString().slice(0, 10) : undefined

function ItineraryMap({ trip, day, onClose, onUpdate, busy, children }: { trip: Itinerary; day: string; onClose: () => void; onUpdate: () => void; busy: boolean; children?: ReactNode }) {
  const [focus, setFocus] = useState('')
  const items = useMemo(() => {
    const ids = trip.days.find(d => d.date === day)?.stop_ids ?? []
    return ids.map(id => trip.stops.find(s => s.id === id)).filter((s): s is Stop => !!s).map(s => ({
      stopId: s.id, destination: { provider_id: s.place.id, name: s.place.name, city: s.place.city, address: s.place.address,
        coordinate: arrivalCoordinate({ place: s.place } as DiscoveryCard) },
    }))
  }, [trip, day])
  const lines = useMemo(() => items.slice(1).map((item, i) => {
    const previous = items[i]
    const actual = trip.route_status !== 'dirty' ? trip.routes.find(r => r.date === day && r.from_id === previous.stopId && r.to_id === item.stopId && r.mode === trip.travel_mode) : undefined
    const a = previous.destination.coordinate, b = item.destination.coordinate
    return { path: actual?.actual && actual.path?.length > 1 ? actual.path : [[a.longitude, a.latitude], [b.longitude, b.latitude]] as [number, number][],
      actual: !!actual?.actual && (actual.path?.length ?? 0) > 1 }
  }), [trip, day, items])
  if (!items.length) return null
  const selectedId = items.some(v => v.destination.provider_id === focus) ? focus : items[0].destination.provider_id
  const segment = Math.max(0, items.findIndex(v => v.destination.provider_id === selectedId)-1)
  const navigation = items[segment+1] ? amapNavigationUrl(items[segment].destination, items[segment+1].destination, trip.travel_mode) : null
  const missing = lines.some(line => !line.actual)
  const routeControls = items.length > 1 && <div className='itinerary-map-controls'>
    <p className='itinerary-map-status' role='status'>{busy ? '正在更新路线…' : trip.route_status === 'dirty'
      ? '顺序已保存 · 路线待更新' : missing ? '部分路段待更新' : `${modeNames[trip.travel_mode]}路线已更新`}</p>
    <div className='itinerary-map-segment'>
      {items.length > 2 ? <select aria-label='选择高德导航路段' value={segment} onChange={e => setFocus(items[Number(e.target.value)+1].destination.provider_id)}>
        {items.slice(1).map((v, i) => <option key={v.stopId} value={i}>{i+1} → {i+2} · {items[i].destination.name} → {v.destination.name}</option>)}
      </select> : <small>{items[0].destination.name} → {items[1].destination.name}</small>}
    </div>
    <div className='item-actions'><button type='button' className={missing ? 'primary-button' : 'text-button'} disabled={busy} onClick={onUpdate} title='按当前顺序更新路线，保留手动安排'>更新{modeNames[trip.travel_mode]}路线</button>
      {navigation && <a className='text-button' href={navigation} target='_blank' rel='noopener noreferrer' title={`导航第${segment+1}段：${items[segment].destination.name}到${items[segment+1].destination.name}`}><ExternalLink size={15} />高德{modeNames[trip.travel_mode]}导航 {segment+1}→{segment+2}</a>}
    </div>
  </div>
  return <LocationMapDialog items={items} selectedId={selectedId} onSelect={v => setFocus(v.destination.provider_id)} onClose={onClose}
    title={`${day} · 行程路线`} lines={lines} numbered routeControls={routeControls}>{children}</LocationMapDialog>
}

export function ItineraryCenter() {
  const { itineraryId } = useParams()
  const { user, initializing } = useAuth()
  const account = user?.username ?? 'guest'
  const owner = useRef(account)
  const navigate = useNavigate(), assistant = useBusinessAssistant()
  const [loaded, setLoaded] = useState<{ owner: string; data: Collection } | null>(null)
  const data = loaded?.owner === account ? loaded.data : null
  const trip = data?.itineraries.find(v => v.id === itineraryId) ?? null
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [loading, setLoading] = useState(true)
  const lock = useRef(false)
  const [creating, setCreating] = useState(false), [name, setName] = useState('新的出游行程')
  const [settings, setSettings] = useState<{ name: string; start: string; end: string; mode: Itinerary['travel_mode']; generate?: boolean } | null>(null)
  const [dragging, setDragging] = useState<string | null>(null), [over, setOver] = useState<string | null>(null)
  const [overDay, setOverDay] = useState<string | null>(null)
  const dragged = useRef<string | null>(null)
  const pointerDrag = useRef<{ pointer: number; x: number; y: number; clientX: number; clientY: number; moved: boolean; valid: boolean; day: string | null; before?: string } | null>(null)
  const dragFrame = useRef(0), board = useRef<HTMLDivElement>(null)
  const previousPositions = useRef(new Map<string, { left: number; top: number }>())
  const [mapDay, setMapDay] = useState<string | null>(null)
  useEffect(() => () => cancelAnimationFrame(dragFrame.current), [])
  useLayoutEffect(() => {
    const positions = previousPositions.current
    previousPositions.current = new Map()
    if (!positions.size || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    board.current?.querySelectorAll<HTMLElement>('[data-itinerary-stop]').forEach(element => {
      const previous = positions.get(element.dataset.itineraryStop!)
      if (!previous) return
      const rect = element.getBoundingClientRect()
      const x = previous.left-rect.left-window.scrollX, y = previous.top-rect.top-window.scrollY
      if (Math.abs(x)+Math.abs(y) > 1) element.animate?.([
        { transform: `translate(${x}px,${y}px)`, opacity: .65 }, { transform: 'translate(0,0)', opacity: 1 },
      ], { duration: 260, easing: 'cubic-bezier(.22,.75,.18,1)' })
    })
  }, [trip?.version])
  const reload = useCallback(async () => {
    const value = await apiClient.get<Collection>('/itineraries')
    if (owner.current === account) { setLoaded({ owner: account, data: value }); setLoading(false) }
    return value
  }, [account])
  useEffect(() => { owner.current = account }, [account])
  useEffect(() => {
    if (initializing) return
    let active = true
    void reload().catch(e => { if (active) { setError(e instanceof Error ? e.message : '行程加载失败。'); setLoading(false) } })
    const changed = () => { void reload().catch(() => undefined) }
    window.addEventListener(itineraryEvent, changed); window.addEventListener(BUSINESS_CHANGED, changed)
    return () => { active = false; window.removeEventListener(itineraryEvent, changed); window.removeEventListener(BUSINESS_CHANGED, changed) }
  }, [initializing, reload])

  function accept(value: Itinerary) {
    if (owner.current !== account) return
    setLoaded(old => old?.owner === account ? { ...old, data: { ...old.data,
      itineraries: old.data.itineraries.some(v => v.id === value.id) ? old.data.itineraries.map(v => v.id === value.id ? value : v) : [value, ...old.data.itineraries] } } : old)
  }
  async function mutate(load: () => Promise<Envelope>, after?: () => void) {
    if (lock.current) return
    lock.current = true; setBusy(true); setError('')
    try { const result = await load(); if (owner.current === account) { accept(result.itinerary); after?.(); announceItinerary() } }
    catch (e) { if (owner.current === account) { setError(e instanceof Error ? e.message : '修改未完成。'); await reload().catch(() => undefined) } }
    finally { lock.current = false; setBusy(false) }
  }
  async function create() {
    await mutate(() => apiClient.post<Envelope>('/itineraries', { name }), () => setCreating(false))
  }
  function saveSettings() {
    if (!trip || !settings) return
    const hasDates = !!settings.start && !!settings.end
    if ((settings.start || settings.end || settings.generate || trip.start_date) && !hasDates) {
      setError('请选择完整的出发和结束日期。'); return
    }
    if (hasDates && (settings.end < settings.start || Date.parse(settings.end)-Date.parse(settings.start) >= 30*86400000)) {
      setError('结束日期应在出发日期之后或当天，一次最多安排30天。'); return
    }
    void mutate(async () => {
      const saved = await apiClient.patch<Envelope>(`/itineraries/${trip.id}`, { version: trip.version,
        name: settings.name, travel_mode: settings.mode,
        ...(hasDates ? { start_date: settings.start, end_date: settings.end } : {}) })
      if (owner.current !== account) return saved
      accept(saved.itinerary); setSettings(null)
      return settings.generate ? apiClient.post<Envelope>(`/itineraries/${trip.id}/generate`, {
        version: saved.itinerary.version, request_id: crypto.randomUUID(), optimize: true,
      }) : saved
    })
  }
  function moveStop(id: string, dayKey: string | null, before?: string) {
    if (!trip || busy) return
    const days = trip.days.map(d => ({ ...d, stop_ids: d.stop_ids.filter(v => v !== id) }))
    const unassigned = trip.unassigned_ids.filter(v => v !== id)
    const destination = dayKey === null ? unassigned : days.find(d => d.date === dayKey)?.stop_ids
    if (!destination || !trip.stops.some(s => s.id === id) || before === id) return
    const index = before ? destination.indexOf(before) : -1
    destination.splice(index >= 0 ? index : destination.length, 0, id)
    previousPositions.current = new Map(Array.from(board.current?.querySelectorAll<HTMLElement>('[data-itinerary-stop]') ?? []).map(element => {
      const rect = element.getBoundingClientRect()
      return [element.dataset.itineraryStop!, { left: rect.left+window.scrollX, top: rect.top+window.scrollY }]
    }))
    // Saving order has no provider dependency. Route fetching is an explicit,
    // separate action after the user finishes all of their edits.
    void mutate(() => apiClient.put<Envelope>(`/itineraries/${trip.id}/order`, { version: trip.version, days, unassigned_ids: unassigned }))
  }
  function nudge(stop: Stop, day: ItineraryDay | null, delta: number) {
    const ids = day?.stop_ids ?? trip?.unassigned_ids ?? []
    const current = ids.indexOf(stop.id), next = current + delta
    if (next < 0 || next >= ids.length) return
    moveStop(stop.id, day?.date ?? null, delta < 0 ? ids[next] : ids[next+1])
  }
  function generate(optimize: boolean) {
    if (!trip) return
    if (!trip.start_date || !trip.end_date) {
      setError(''); setSettings({ name: trip.name, start: '', end: '', mode: trip.travel_mode, generate: true }); return
    }
    void mutate(() => apiClient.post<Envelope>(`/itineraries/${trip.id}/generate`,
      { version: trip.version, request_id: crypto.randomUUID(), optimize }))
  }
  function trackDrag() {
    const active = pointerDrag.current
    if (!active?.moved) return
    const edge = 80, height = window.innerHeight
    const speed = active.clientY < edge ? -Math.min(14, (edge-active.clientY)/5)
      : active.clientY > height-edge ? Math.min(14, (active.clientY-height+edge)/5) : 0
    if (speed) window.scrollBy(0, speed)
    const at = document.elementFromPoint(active.clientX, active.clientY)
    const row = at?.closest<HTMLElement>('[data-itinerary-stop]')
    const group = at?.closest<HTMLElement>('[data-itinerary-day]')
    active.valid = !!group && !!board.current?.contains(group)
    if (active.valid && group) {
      active.day = group.dataset.itineraryDay || null
      active.before = row?.dataset.itineraryStop
      setOver(active.before ?? null); setOverDay(group.dataset.itineraryDay ?? '')
    } else { setOver(null); setOverDay(null) }
    dragFrame.current = requestAnimationFrame(trackDrag)
  }
  function endDrag() {
    cancelAnimationFrame(dragFrame.current)
    pointerDrag.current = null; dragged.current = null; setDragging(null); setOver(null); setOverDay(null)
  }
  useCommandTarget('itinerary', () => ({ itinerary_id: trip?.id, itinerary_version: trip?.version,
    page_loading: loading || busy, layer: mapDay ? 'map' : 'itinerary' }), effect => {
    if (effect.tool === 'itinerary_result') { accept(effect.arguments.itinerary as Itinerary); return true }
    if (effect.tool === 'close_layer' && mapDay) { setMapDay(null); return true }
    if (effect.tool === 'show_itinerary_map' && trip) {
      const day = trip.days.find(d => d.date === effect.arguments.date) ?? trip.days.find(d => d.stop_ids.length)
      if (!day) throw new Error('请先把地点安排到具体日期。')
      setMapDay(day.date); return true
    }
    return false
  })
  function stopRow(id: string, day: ItineraryDay | null, index: number) {
    const stop = trip?.stops.find(s => s.id === id)
    if (!stop || !trip) return null
    const forecast = day && trip.weather[id]?.days.find(v => v.date === day.date)
    const route = day && index > 0 && trip.route_status !== 'dirty' ? trip.routes.find(r => r.date === day.date && r.from_id === day.stop_ids[index-1] && r.to_id === id) : undefined
    return <div key={id} className='itinerary-stop-wrap'>
      {route && <p className='itinerary-leg'>{route.actual ? `${modeNames[trip.travel_mode]} ${Number(route.distance_km?.toFixed(1))} 公里 · 约${Math.round(route.duration_minutes ?? 0)}分钟` : '该路段道路数据暂不可用'}</p>}
      <article className='itinerary-stop' data-itinerary-stop={id} data-itinerary-day={day?.date ?? ''} data-dragging={dragging === id} data-over={over === id}
        onDragOver={e => { e.preventDefault(); if (dragged.current !== id) setOver(id) }}
        onDrop={e => { e.preventDefault(); e.stopPropagation(); if (dragged.current) moveStop(dragged.current, day?.date ?? null, id); dragged.current = null; setDragging(null); setOver(null) }}>
        <button type='button' className='itinerary-grip' disabled={busy} draggable={!busy} aria-label={`拖动${stop.place.name}`} title='按住拖动，可换顺序或移到其他日期'
          onPointerDown={e => {
            if (busy || e.button !== 0) return
            e.preventDefault(); dragged.current = id
            pointerDrag.current = { pointer: e.pointerId, x: e.clientX, y: e.clientY, clientX: e.clientX, clientY: e.clientY, moved: false, valid: false, day: day?.date ?? null, before: id }
            e.currentTarget.setPointerCapture(e.pointerId)
          }}
          onPointerMove={e => {
            const active = pointerDrag.current
            if (!active || active.pointer !== e.pointerId) return
            if (!active.moved && Math.hypot(e.clientX-active.x, e.clientY-active.y) < 6) return
            active.clientX = e.clientX; active.clientY = e.clientY
            if (!active.moved) { active.moved = true; setDragging(id); trackDrag() }
          }}
          onPointerUp={e => {
            const active = pointerDrag.current
            endDrag()
            if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId)
            if (active?.moved && active.valid) moveStop(id, active.day, active.before)
          }}
          onPointerCancel={endDrag}
          onDragStart={e => { dragged.current = id; setDragging(id); e.dataTransfer.setData('text/plain', id); e.dataTransfer.effectAllowed = 'move' }}
          onDragEnd={endDrag}><GripVertical size={18} /><span>拖动</span></button>
        <span className='itinerary-stop-number'>{index+1}</span><div className='itinerary-stop-content'>
          <h3>{stop.place.name}</h3><p>{stop.place.city} · {placeType(stop.place.map_type)}</p>
          {forecast && <p className='itinerary-weather'>{forecast.condition} · {forecast.temp_min_c}–{forecast.temp_max_c}°C{forecast.precipitation_mm > 0 ? ` · 降水${forecast.precipitation_mm}mm` : ''}</p>}
          <div className='itinerary-stop-actions'>
            <button className='text-button' type='button' disabled={busy || index === 0} aria-label={`上移${stop.place.name}`} title='上移' onClick={() => nudge(stop, day, -1)}><ArrowUp size={14} /></button>
            <button className='text-button' type='button' disabled={busy || index === (day?.stop_ids.length ?? trip.unassigned_ids.length)-1} aria-label={`下移${stop.place.name}`} title='下移' onClick={() => nudge(stop, day, 1)}><ArrowDown size={14} /></button>
            <label><span className='sr-only'>安排{stop.place.name}的日期</span><select disabled={busy} value={day?.date ?? ''} onChange={e => moveStop(id, e.target.value || null)}>
              <option value=''>待安排</option>{trip.days.map((v, i) => <option key={v.date} value={v.date}>第{i+1}天 · {v.date}</option>)}
            </select></label>
            <button type='button' className='text-button' disabled={busy} aria-label={`移出${stop.place.name}`} title='从行程移出，保留收藏和历史'
              onClick={() => void mutate(() => apiClient.remove<Envelope>(`/itineraries/${trip.id}/stops/${id}?version=${trip.version}`))}><X size={14} /></button>
          </div>
        </div>
      </article>
    </div>
  }
  return <section className='personal-page itinerary-center'>
    <header className='page-heading'><div><h1>行程中心</h1></div>
      <button className='primary-button' type='button' onClick={() => setCreating(true)} disabled={busy}><Plus size={16} />新建行程</button>
    </header>
    {error && !settings && <p role='alert' className='error-banner'>{error}<button className='text-button' onClick={() => void reload()}>刷新行程</button></p>}
    {loading && <p role='status'>正在加载行程…</p>}
    {!loading && !trip && <div className='itinerary-list'>
      {data?.itineraries.map(v => <Link key={v.id} to={`/itineraries/${v.id}`} className='itinerary-summary glass-panel' viewTransition>
        <h2>{v.name}</h2><p>{v.start_date ? `${v.start_date} 至 ${v.end_date}` : '日期待确定'}</p><span>{v.stops.length} 个地点 · {modeNames[v.travel_mode]}</span>
      </Link>)}
      {!data?.itineraries.length && <div className='itinerary-empty glass-panel'><h2>下一段旅程，从想去的地点开始</h2><p>创建行程后，推荐和收藏中的地点都可以加入。</p><Link className='text-button' to='/explore'>去发现地点 →</Link></div>}
    </div>}
    {trip && <>
      <nav className='itinerary-switcher' aria-label='切换行程'><Link to='/itineraries'>全部行程</Link>{data?.itineraries.map(v => <Link key={v.id} aria-current={v.id === trip.id ? 'page' : undefined} to={`/itineraries/${v.id}`}>{v.name}</Link>)}</nav>
      <header className='itinerary-heading glass-panel'><div><h2>{trip.name}</h2><p>{trip.start_date ? `${trip.start_date} 至 ${trip.end_date}` : '先收集地点，再确定日期'} · {modeNames[trip.travel_mode]} · {trip.stops.length} 个地点</p></div>
        <button className='text-button' disabled={busy} onClick={() => { setError(''); setSettings({ name: trip.name, start: trip.start_date ?? '', end: trip.end_date ?? '', mode: trip.travel_mode }) }}>行程设置</button>
      </header>
      <div className='itinerary-toolbar'>
        <button type='button' className='primary-button' disabled={busy || !trip.stops.length} onClick={() => generate(true)}>{busy ? '正在处理…' : trip.generated_at ? '重新自动安排' : '自动安排行程'}</button>
        <button type='button' className='text-button' disabled={busy || !trip.days.some(d => d.stop_ids.length)} onClick={() => generate(false)}>更新路线</button>
        <span role='status'>{busy ? '正在保存或生成路线，请稍候' : trip.route_status === 'dirty' ? '安排已保存 · 路线待更新' : trip.generated_at ? '路线已更新' : '地点已保存'}</span>
      </div>
      {!!trip.notices.length && <div className='itinerary-notices'>{trip.notices.map(v => <p key={v}>{v}</p>)}</div>}
      {(trip.stops.length > 0 || trip.days.length > 0) && <div className='itinerary-board glass-panel' ref={board} data-dragging={!!dragging}>
      <header className='itinerary-board-heading'><h2>行程安排</h2><p><GripVertical size={15} />按住“拖动”调整顺序或跨日期移动，完成后更新路线</p></header>
      {!!trip.unassigned_ids.length && <section className='itinerary-day' data-itinerary-day='' data-drop-active={!!dragging && overDay === ''} aria-label='待安排地点' onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (dragged.current) moveStop(dragged.current, null); endDrag() }}>
        <header><h2>待安排</h2><span>{trip.unassigned_ids.length} 个地点</span></header><div className='itinerary-day-places'>{trip.unassigned_ids.map((id, i) => stopRow(id, null, i))}</div>
      </section>}
      {trip.days.map((day, i) => <section key={day.date} className='itinerary-day' data-itinerary-day={day.date} data-drop-active={!!dragging && overDay === day.date} aria-label={`${day.date}的行程`}
        onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (dragged.current) moveStop(dragged.current, day.date); endDrag() }}>
        <header><div><h2>第{i+1}天</h2><p>{day.date}</p></div><button className='text-button' type='button' disabled={!day.stop_ids.length} onClick={() => setMapDay(day.date)}><MapIcon size={16} />当天地图</button></header>
        <div className='itinerary-day-places'>
        {day.stop_ids.map((id, index) => stopRow(id, day, index))}
        {!day.stop_ids.length ? <p className='itinerary-drop-hint itinerary-day-drop'>把地点拖到这里，安排到第{i+1}天</p> : <div className='itinerary-day-tail' aria-hidden='true'>放到当天最后</div>}
        </div>
      </section>)}</div>}
      {trip.generated_at && <p className='muted itinerary-footnote'>路线更新于 {new Date(trip.generated_at).toLocaleString('zh-CN')}</p>}
      {!trip.stops.length && <p className='itinerary-drop-hint'><Link className='text-button' to='/explore'>从推荐中加入地点</Link>，也可以从收藏加入。</p>}
    </>}
    {creating && <OverlayHost label='新建行程' onClose={() => { if (!busy) setCreating(false) }} panelClassName='itinerary-dialog glass-panel'>
      <h2>新建行程</h2><form onSubmit={e => { e.preventDefault(); void create() }}><label className='field'>行程名称<input autoFocus required maxLength={100} value={name} onChange={e => setName(e.target.value)} /></label>
        <div className='item-actions'><button className='text-button' type='button' disabled={busy} onClick={() => setCreating(false)}>取消</button><button className='primary-button' disabled={busy}>创建行程</button></div>
      </form>
    </OverlayHost>}
    {settings && trip && <OverlayHost label='行程设置' onClose={() => { if (!busy) setSettings(null) }} panelClassName='itinerary-dialog glass-panel'>
      <h2>{settings.generate ? '准备安排行程' : '行程设置'}</h2><form onSubmit={e => { e.preventDefault(); saveSettings() }}>
        <label className='field'>行程名称<input required maxLength={100} value={settings.name} onChange={e => setSettings({ ...settings, name: e.target.value })} /></label>
        <div className='itinerary-date-fields'><label className='field'>出发日期<input required={settings.generate || !!settings.end || !!trip.start_date} type='date' value={settings.start} onChange={e => setSettings({ ...settings, start: e.target.value,
          end: e.target.value && (!settings.end || settings.end < e.target.value) ? e.target.value : settings.end })} /></label>
          <label className='field'>结束日期<input required={settings.generate || !!settings.start} type='date' min={settings.start} max={lastDate(settings.start)} value={settings.end} onChange={e => setSettings({ ...settings, end: e.target.value })} /></label></div>
        {!settings.generate && !trip.start_date && <p className='muted itinerary-setting-hint'>日期可稍后确定。</p>}
        <fieldset className='itinerary-modes'><legend>地点之间的交通方式</legend><div>{Object.entries(modeNames).map(([value, label]) => {
          const Icon = modeIcons[value as Itinerary['travel_mode']]
          return <label key={value} className='text-button' data-selected={settings.mode === value}>
            <input type='radio' name='itinerary-mode' value={value} checked={settings.mode === value} onChange={() => setSettings({ ...settings, mode: value as Itinerary['travel_mode'] })} /><Icon size={18} />{label}
          </label>
        })}</div></fieldset>
        {error && <p role='alert' className='field-error'>{error}</p>}
        <div className='item-actions'><button type='button' className='text-button' disabled={busy} onClick={() => setSettings(null)}>取消</button><button className='primary-button' disabled={busy}>{settings.generate ? '保存并自动安排' : '保存设置'}</button></div>
      </form>
    </OverlayHost>}
    {mapDay && trip && <ItineraryMap trip={trip} day={mapDay} onClose={() => setMapDay(null)} busy={busy} onUpdate={() => generate(false)}>{assistant?.chat}</ItineraryMap>}
    <button className='text-button itinerary-back' type='button' onClick={() => navigate('/explore')}>继续发现地点 →</button>
  </section>
}
