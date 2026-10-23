import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { MapPin, X } from 'lucide-react'
import { apiClient } from '../api/client'
import type { Coordinate } from '../api/types'
import { useAuth } from '../features/auth/authContext'
import { Composer } from '../features/studio/Composer'
import { OverlayHost } from '../features/studio/OverlayHost'
import { LayerConversation } from '../features/studio/LayerConversation'
import { useDetailTransition } from '../features/studio/useDetailTransition'
import { LocationMapDialog } from '../features/search/LocationMapDialog'
import { useBusinessAssistant, useCommandTarget } from '../features/commands/commandContext'
import type { DiscoveryCard, DiscoverySnapshot } from '../features/discovery/types'
import { DiscoveryRail } from '../features/discovery/DiscoveryRail'
import '../styles/discovery.css'

const modes: Record<string, string> = { walking: '步行', bicycling: '骑行', driving: '驾车' }
const comparisonId = '__discovery_comparison__'
const nextFrame = () => new Promise<void>(resolve => requestAnimationFrame(() => resolve()))

function RouteFact({ card }: { card: DiscoveryCard }) {
  if (!card.route || card.route.unavailable || card.route.distance_km === undefined) return null
  return <span>{modes[card.route.mode ?? ''] ?? ''} {card.route.distance_km} km{card.route.duration_minutes !== undefined && ` · 约${Math.round(card.route.duration_minutes)}分钟`}</span>
}

function PlaceFacts({ card }: { card: DiscoveryCard }) {
  const hours = card.place.facts.opentime_week || card.place.facts.opentime_today
  const cost = card.place.facts.cost?.trim()
  return <>
    {hours && <div><dt>开放时间</dt><dd>{hours}</dd></div>}
    {cost && <div><dt>参考消费</dt><dd>{/^\d+(\.\d+)?$/.test(cost) ? `¥${cost} / 人` : cost}</dd></div>}
  </>
}

export function DiscoveryPage({ initialSnapshot, initialMessage, archiveHistoryId }: {
  initialSnapshot?: DiscoverySnapshot; initialMessage?: string; archiveHistoryId?: string
} = {}) {
  const { initializing, user } = useAuth()
  const navigation = useNavigate()
  const incoming = useLocation().state as { discoveryJobId?: string; discoveryMessage?: string } | null
  const assistant = useBusinessAssistant()
  const [job, setJob] = useState<DiscoverySnapshot | null>(initialSnapshot ?? null)
  const [jobId, setJobId] = useState<string | null>(incoming?.discoveryJobId ?? null)
  const [busy, setBusy] = useState(!!incoming?.discoveryJobId)
  const [locating, setLocating] = useState(false)
  const [error, setError] = useState('')
  const [requestText, setRequestText] = useState(initialMessage ?? incoming?.discoveryMessage ?? '')
  const [location, setLocation] = useState<Coordinate | undefined>()
  const [detailId, setDetailId] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const selection = useRef<string[]>([])
  function choose(ids: string[]) { selection.current = ids; setSelectedIds(ids) }
  const [messages, setMessages] = useState<{ id: string; role: string; content: string }[]>([])
  const serial = useRef(0), activeId = useRef<string | null>(initialSnapshot?.id ?? null)
  const pendingId = useRef<string | null>(incoming?.discoveryJobId ?? null)
  const pendingMessage = useRef(incoming?.discoveryMessage ?? '')
  const locationAttempt = useRef(0)
  const automaticLocationUsed = useRef(false)
  const locateCurrent = useRef<(message: string, sequence: number) => Promise<void>>(async () => {})
  const transcript = useRef<HTMLDivElement>(null)
  const workspace = useRef<HTMLDivElement>(null), inputDock = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const dock = inputDock.current, page = workspace.current
    if (!dock || !page) return
    let frame = 0
    const measure = () => {
      const space = `${Math.ceil(dock.getBoundingClientRect().height + (parseFloat(getComputedStyle(dock).bottom) || 20) + 28)}px`
      if (page.style.getPropertyValue('--discovery-dock-space') !== space) page.style.setProperty('--discovery-dock-space', space)
    }
    const resized = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(measure) }
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(resized)
    observer?.observe(dock); measure(); window.addEventListener('resize', measure)
    return () => { observer?.disconnect(); cancelAnimationFrame(frame); window.removeEventListener('resize', measure) }
  }, [])
  useLayoutEffect(() => { if (transcript.current) transcript.current.scrollTop = transcript.current.scrollHeight }, [messages.length])
  const alive = useRef(true)
  const authReady = useRef(!initializing)
  const owner = useRef(user?.username ?? null)
  const ownerKnown = useRef(!initializing)
  const savingHistory = useRef(new Set<string>())
  const historyPending = useRef(false)
  useEffect(() => { authReady.current = !initializing }, [initializing])
  useEffect(() => {
    if (initializing) return
    if (!ownerKnown.current) { ownerKnown.current = true; owner.current = user?.username ?? null; return }
    if (owner.current === (user?.username ?? null)) return
    const guestLogin = owner.current === null && !!user?.username
    owner.current = user?.username ?? null
    if (guestLogin) { setError(''); return }
    serial.current++; locationAttempt.current++; activeId.current = null; pendingId.current = null
    setLocating(false)
    setJob(null); setJobId(null); setBusy(false); setMessages([]); setDetailId(null); setLocation(undefined); choose([])
  }, [user?.username, initializing])
  useEffect(() => {
    if (!user || !job || !job.cards.length || !['completed', 'partial'].includes(job.status) || job.history_id || savingHistory.current.has(job.id)) return
    const account = user.username, id = job.id
    savingHistory.current.add(id)
    historyPending.current = true
    void apiClient.post<{ history_id: string }>(`/discovery/jobs/${id}/history`).then(async saved => {
      if (owner.current === account) setJob(current => current?.id === id ? { ...current, history_id: saved.history_id } : current)
      await nextFrame()
    }).catch(() => { savingHistory.current.delete(id) }).finally(() => { historyPending.current = false })
  }, [user, job])
  const layers = useDetailTransition(detailId, version, setDetailId)
  const selected = job?.cards.find(card => card.place.id === detailId)
  const commands = useRef(assistant)
  const currentLayers = useRef(layers)
  useLayoutEffect(() => { commands.current = assistant; currentLayers.current = layers })
  const queryShown = useRef<string | null>(initialSnapshot?.id ?? null)
  useCommandTarget('discovery', () => ({
    page_loading: historyPending.current,
    discovery_job_id: job?.id, history_id: job?.history_id ?? archiveHistoryId,
    result_version: version, focused_id: selected?.place.id,
    selected_ids: selection.current, layer: layers.mapOpen ? 'map' : detailId ? 'detail' : 'results',
    visible_places: job?.cards.map(card => ({ id: card.place.id, name: card.place.name })) ?? [],
    conversation: messages.slice(-6).map(({ role, content }) => ({ role, content })),
  }), async effect => {
    const args = effect.arguments
    if (effect.tool === 'chat_started') {
      setMessages(current => current.at(-1)?.content === args.message ? current : [...current,
        { id: String(args.requestId), role: 'user', content: String(args.message) }].slice(-12))
    } else if (['chat_reply', 'chat_failed'].includes(effect.tool)) {
      setMessages(current => [...current, { id: String(args.requestId) + '-reply', role: 'assistant',
        content: String(args.reply ?? args.message) }].slice(-12))
    } else if (effect.tool === 'clear_conversation') setMessages([])
    else if (effect.tool === 'close_layer') {
      if (layers.mapOpen) layers.closeMap()
      else if (detailId) layers.close()
      else return false
    } else if (effect.tool === 'open_detail' || effect.tool === 'open_map') {
      const id = String(args.id)
      if (!job?.cards.some(card => card.place.id === id)) throw new Error('该地点已不在当前结果中。')
      if (detailId !== id) {
        if (detailId) throw new Error('请先返回当前详情，再打开其他地点。')
        // The next action needs the committed detail before adding map history.
        // A requestAnimationFrame alone does not finish concurrent React work.
        flushSync(() => layers.open(id))
      }
      if (effect.tool === 'open_map') currentLayers.current.openMap()
    } else if (effect.tool === 'select_candidates') {
      const ids = args.ids as string[]
      if (ids.length > 3 || ids.some(id => !job?.cards.some(card => card.place.id === id)))
        throw new Error('请选择当前结果中的至多三个地点。')
      flushSync(() => choose(ids))
    } else if (effect.tool === 'show_comparison') {
      const ids = (args.ids as string[] | undefined) ?? selection.current
      if (ids.length < 2 || ids.length > 3 || new Set(ids).size !== ids.length ||
        ids.some(id => !job?.cards.some(card => card.place.id === id))) throw new Error('请选择当前结果中的两个或三个地点再比较。')
      if (detailId) throw new Error('请先返回推荐结果，再查看比较。')
      flushSync(() => { choose(ids); layers.open(comparisonId) })
    } else if (effect.tool === 'show_candidates') {
      document.querySelector<HTMLElement>('.discovery-rail')?.focus()
    } else if (effect.tool === 'start_team_pick' || effect.tool === 'end_team_pick') {
      document.querySelector<HTMLElement>('.discovery-rail')?.focus()
    } else return false
    return true
  })
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false; if (pendingId.current) void apiClient.remove(`/discovery/jobs/${pendingId.current}`).catch(() => undefined) }
  }, [])
  useEffect(() => {
    if (!jobId || !busy) return
    let stopped = false
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const next = await apiClient.get<DiscoverySnapshot>(`/discovery/jobs/${jobId}`)
        if (stopped) return
        if (next.intent === 'business') {
          if (next.status === 'running') { timer = setTimeout(() => void poll(), 650); return }
          const sequence = serial.current
          const message = pendingMessage.current
          pendingId.current = null
          setBusy(false); setJobId(null)
          await nextFrame()
          let handedOff = false
          try {
            if (!alive.current || sequence !== serial.current) return
            if (next.status !== 'completed') { setError('本轮操作理解未完成，可以重新发送。'); return }
            if (!commands.current) { setError('操作入口尚未准备好。'); return }
            handedOff = true
            await commands.current.send(message, { intakeId: jobId })
          }
          catch (caught) {
            if (alive.current && sequence === serial.current)
              setError(caught instanceof Error ? caught.message : '操作未完成。')
          }
          finally { if (!handedOff) void apiClient.remove(`/discovery/jobs/${jobId}`).catch(() => undefined) }
          return
        }
        if (archiveHistoryId && next.intent === 'search') {
          pendingId.current = null // Ownership moves to the new page; do not cancel its job on unmount.
          navigation('/explore', { state: { discoveryJobId: jobId, discoveryMessage: pendingMessage.current }, viewTransition: true })
          return
        }
        // Keep the previous card objects and history layer while intent is unknown.
        if (next.intent !== null) {
          if (queryShown.current !== jobId) {
            queryShown.current = jobId; activeId.current = jobId
            setRequestText(pendingMessage.current); setDetailId(null); choose([])
            setVersion(value => value + 1)
          }
          setJob(next)
        }
        if (next.status !== 'running') {
          pendingId.current = null
          setBusy(false)
          if (next.intent === null && !activeId.current) {
            setRequestText(pendingMessage.current)
            // Preserve the owned failed conversation for natural follow-ups.
            activeId.current = jobId
          }
          if (next.request_location && next.status === 'completed' && !next.context.origin) {
            if (!automaticLocationUsed.current) {
              automaticLocationUsed.current = true
              void locateCurrent.current(pendingMessage.current, serial.current)
            } else setError('定位后查询尚未继续，可以重新发送这次想法。')
          } else if (next.reply) setMessages(current => [...current, { id: next.id, role: 'assistant', content: next.reply }].slice(-12))
          return
        }
        timer = setTimeout(() => void poll(), 650)
      } catch (caught) {
        if (!stopped) { setBusy(false); setError(caught instanceof Error ? caught.message : '查询中断。') }
      }
    }
    void poll()
    return () => { stopped = true; clearTimeout(timer) }
  }, [jobId, busy, archiveHistoryId, navigation])

  async function send(message: string, point = location, locationContinuation = false) {
    const sequence = ++serial.current
    if (!locationContinuation) automaticLocationUsed.current = false
    locationAttempt.current++; setLocating(false)
    const previousId = activeId.current
    if (pendingId.current) await apiClient.remove(`/discovery/jobs/${pendingId.current}`).catch(() => undefined)
    if (!alive.current || sequence !== serial.current) return
    setError(''); setJobId(null); setBusy(true)
    pendingMessage.current = message
    if (!locationContinuation) setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user', content: message }].slice(-12))
    try {
      const waitingSince = Date.now()
      while (!authReady.current) {
        if (Date.now() - waitingSince > 10000) throw new Error('登录状态尚未确认，可以稍后重试。')
        await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
      }
      if (!alive.current || sequence !== serial.current) return
      const started = await apiClient.post<{ id: string }>('/discovery/jobs', {
        message, previous_id: previousId, ...(point ? { location: point } : {}),
        ...(commands.current ? { view: { focused_id: selected?.place.id ?? null,
          selected_ids: selection.current, layer: layers.mapOpen ? 'map' : detailId ? 'detail' : 'results' } } : {}),
        ...(commands.current && messages.length ? { conversation: messages.slice(-6).map(({ role, content }) => ({ role, content })) } : {}),
      })
      if (!alive.current || sequence !== serial.current) {
        void apiClient.remove(`/discovery/jobs/${started.id}`).catch(() => undefined); return
      }
      pendingId.current = started.id; setJobId(started.id)
    } catch (caught) {
      if (sequence === serial.current && alive.current) {
        setBusy(false); setError(caught instanceof Error ? caught.message : '查询未完成。')
      }
      throw caught
    }
  }

  async function locate(message = requestText, sequence = serial.current) {
    const attempt = ++locationAttempt.current
    setError(''); setLocating(true)
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }))
      const point = { longitude: position.coords.longitude, latitude: position.coords.latitude, system: 'wgs84' }
      if (!alive.current || sequence !== serial.current || attempt !== locationAttempt.current) return
      setLocation(point)
      if (message) await send(message, point, true)
    } catch (caught) {
      if (alive.current && sequence === serial.current && attempt === locationAttempt.current) {
        const denied = (caught as GeolocationPositionError | undefined)?.code === 1
        setError(denied ? '未允许定位。可以重试授权，或在对话里说出发地。' : '暂未取得位置。可以重试定位，或在对话里说出发地。')
      }
    } finally {
      if (alive.current && attempt === locationAttempt.current) setLocating(false)
    }
  }
  useLayoutEffect(() => { locateCurrent.current = locate })

  const chat = <LayerConversation label='继续聊这次出游' focusedPlace={selected?.place.name ?? 'RoamBot'}
    messages={messages} status={busy ? job?.stage ?? '' : ''} busy={busy || !!assistant?.busy} onSend={send} />
  const mapItem = selected ? { destination: { provider_id: selected.place.id, name: selected.place.name,
    city: selected.place.city, address: selected.place.address, coordinate: selected.place.coordinate } } : null
  return <div className='discovery-workspace' ref={workspace}>
    <header className='discovery-intro'>
      <p className='eyebrow'>ROAMBOT · 随心去发现</p>
      <h1>{requestText || '这次，你想去做什么？'}</h1>
      {!requestText && <p>一个念头就可以开始。</p>}
      <div className='discovery-context'>
        {job?.center_name && <span><MapPin size={14} />{job.center_name}</span>}
        {job?.context.region && <span>{job.context.region}</span>}
        {job?.context.max_distance_km && <span>实际路程 {job.context.max_distance_km} km 内</span>}
        {job?.context.start_date && <span>{job.context.start_date} 至 {job.context.end_date}</span>}
      </div>
    </header>
    <div className='discovery-status' aria-live='polite'>
      {busy && <p role='status'>{job?.stage || '正在理解这次想法…'}</p>}
      {locating && <p role='status'>正在获取当前位置…</p>}
      {!busy && !locating && !job?.request_location && !job?.cards.length && job?.reply && <p>{job.reply}</p>}
      {error && <p role='alert'>{error}</p>}
      {job?.request_location && !busy && !locating && <button type='button' className='text-button' onClick={() => void locate()}>重试定位</button>}
      {(busy || locating) && <button type='button' className='text-button' onClick={() => { serial.current++; locationAttempt.current++; setLocating(false); if (pendingId.current) void apiClient.remove(`/discovery/jobs/${pendingId.current}`).catch(() => undefined); pendingId.current = null; setBusy(false) }}>停止查找</button>}
    </div>
    <DiscoveryRail>
      {job?.cards.map((card, index) => <article key={card.place.id} className='discovery-card glass-panel' data-place-id={card.place.id}>
        <button type='button' className='discovery-card-open' aria-label={`了解${card.place.name}`} onClick={() => layers.open(card.place.id)} />
        <div className='discovery-card-heading'><span className='discovery-experience'>{card.place.map_type.split(';').filter(Boolean).at(-1) || card.place.city}</span><span className='discovery-card-number'>{String(index + 1).padStart(2, '0')}</span></div>
        <h2>{card.place.name}</h2>
        <p className='discovery-card-city'><MapPin size={13} />{card.place.city}</p>
        <dl className='discovery-card-info discovery-place-facts'><PlaceFacts card={card} /></dl>
        <div className='discovery-facts'><RouteFact card={card} />
          {Array.isArray(card.weather) && card.weather.length > 0 && <span>{card.weather[0].date} · {card.weather[0].condition} · {card.weather[0].temp_min_c}–{card.weather[0].temp_max_c}°C</span>}
        </div>
        <footer>
          <button type='button' className='text-button' aria-pressed={selectedIds.includes(card.place.id)} onClick={() => choose(selection.current.includes(card.place.id)
            ? selection.current.filter(id => id !== card.place.id) : selection.current.length < 3 ? [...selection.current, card.place.id] : selection.current)}>{selectedIds.includes(card.place.id) ? '已选入比较' : '加入比较'}</button>
          <span className='discovery-card-hint' aria-hidden='true'>查看详情 ↗</span>
        </footer>
      </article>)}
    </DiscoveryRail>
    <div className='discovery-input' ref={inputDock}>
      {!!messages.length && <div className='discovery-conversation studio-conversation' ref={transcript} role='log' aria-label='本次对话记录' tabIndex={0}>
        {messages.map(message => <p className={message.role} key={message.id}>{message.content}</p>)}
      </div>}
      <Composer busy={busy || !!assistant?.busy} onSend={send} />
      {assistant?.resultLink && <a href={assistant.resultLink} target='_blank' rel='noreferrer'>打开刚生成的链接</a>}
      {!requestText && <Link to='/recommend' viewTransition>原有查询</Link>}
    </div>
    {!!selectedIds.length && <div className='discovery-selection glass-panel'>
      <span>已选 {selectedIds.length} 个地点</span>
      <button type='button' className='text-button' disabled={selectedIds.length < 2} onClick={() => layers.open(comparisonId)}>查看对比</button>
      <button type='button' className='primary-button' disabled={selectedIds.length < 2 || !!assistant?.busy} onClick={() => void assistant?.send('用选中的地点发起同行计划').catch(() => undefined)}>发起同行计划</button>
    </div>}
    {detailId === comparisonId && <OverlayHost label='地点对比' onClose={layers.close} panelClassName='discovery-detail glass-panel' accessory={chat}>
      <button className='icon-button discovery-close' aria-label='返回推荐' onClick={layers.close}><X size={20} /></button>
      <h2>地点对比</h2><DiscoveryRail label='对比地点'>
        {job?.cards.filter(card => selectedIds.includes(card.place.id)).map(card => <article className='discovery-card glass-panel' key={card.place.id}>
          <p className='eyebrow'>{card.experience}</p><h3>{card.place.name}</h3>
          <p className='discovery-address'>{card.place.address}</p><RouteFact card={card} />
          {Array.isArray(card.weather) && card.weather.map(day => <p key={day.date}>{day.date} · {day.condition} · {day.temp_min_c}–{day.temp_max_c}°C</p>)}
        </article>)}
      </DiscoveryRail>
    </OverlayHost>}
    {selected && <OverlayHost label={`${selected.place.name}详情`} onClose={layers.close} panelClassName='discovery-detail glass-panel' accessory={chat}>
      <button className='icon-button discovery-close' aria-label='返回推荐' onClick={layers.close}><X size={20} /></button>
      <p className='eyebrow'>{selected.experience}</p><h2>{selected.place.name}</h2>
      <p>{selected.place.city} · {selected.place.address}</p>
      <div className='discovery-facts'><RouteFact card={selected} /></div>
      <button type='button' className='text-button' onClick={layers.openMap}>查看位置</button>
      <dl className='discovery-card-info discovery-place-facts'><PlaceFacts card={selected} /></dl>
    </OverlayHost>}
    {layers.mapOpen && mapItem && <LocationMapDialog items={[mapItem]} selectedId={mapItem.destination.provider_id} onClose={layers.closeMap}>{chat}</LocationMapDialog>}
  </div>
}
