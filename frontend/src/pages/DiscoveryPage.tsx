import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'
import { Map, MapPin, X } from 'lucide-react'
import { apiClient, ApiError } from '../api/client'
import type { Coordinate, PlaceSuggestion } from '../api/types'
import { useAuth } from '../features/auth/authContext'
import { Composer } from '../features/studio/Composer'
import { OverlayHost } from '../features/studio/OverlayHost'
import { LayerConversation } from '../features/studio/LayerConversation'
import { useDetailTransition } from '../features/studio/useDetailTransition'
import { LocationMapDialog } from '../features/search/LocationMapDialog'
import { useBusinessAssistant, useCommandTarget } from '../features/commands/commandContext'
import type { DiscoveryCard, DiscoverySnapshot, DiscoveryLocationDetails } from '../features/discovery/types'
import { DiscoveryLocationPill } from '../features/discovery/DiscoveryLocationPill'
import { DiscoveryRail } from '../features/discovery/DiscoveryRail'
import { DiscoveryCardSummary, DiscoveryCardDetails } from '../features/discovery/DiscoveryCardContent'
import { DiscoveryWaiting } from '../features/discovery/DiscoveryWaiting'
import { useDiscoveryLayoutMotion } from '../features/discovery/useDiscoveryLayoutMotion'
import { DiscoveryComparison } from '../features/discovery/DiscoveryComparison'
import { DiscoveryPlanControl } from '../features/discovery/DiscoveryPlanControl'
import { DiscoveryFavoriteControl } from '../features/discovery/DiscoveryFavoriteControl'
import { DiscoveryMapCard } from '../features/discovery/DiscoveryMapCard'
import { PlaceTypeArtwork } from '../components/PlaceTypeArtwork'
import { PlaceGuideLink } from '../components/PlaceGuideLink'
import { AmapLogo } from '../components/AmapLogo'
import { activityLabel, discoveryTitle, arrivalCoordinate, placeArea, placeType, routeLabel } from '../features/discovery/discoveryPresentation'
import { useSessionMessages } from '../features/commands/useSessionMessages'
import { readSavedDiscovery, restoreDiscoveryResult, saveDiscoveryReference } from '../features/discovery/restoreDiscoveryResult'
import { AddToItinerary } from '../features/itineraries/ItineraryProvider'
import '../styles/discovery.css'

const comparisonId = '__discovery_comparison__'
const mapOverviewId = '__discovery_map__'
const nextFrame = () => new Promise<void>(resolve => requestAnimationFrame(() => resolve()))

function RouteFact({ card }: { card: DiscoveryCard }) {
  const text = routeLabel(card)
  return text ? <span>{text}</span> : null
}

export function DiscoveryPage({ initialSnapshot, initialMessage, archiveHistoryId }: {
  initialSnapshot?: DiscoverySnapshot; initialMessage?: string; archiveHistoryId?: string
} = {}) {
  const { initializing, user } = useAuth()
  const navigation = useNavigate()
  const incoming = useLocation().state as { discoveryJobId?: string; discoveryMessage?: string; discoverySelectedIds?: string[]; initialIdea?: string; startTeamPick?: boolean; homeEntry?: boolean } | null
  const assistant = useBusinessAssistant()
  const { workspace: workspaceRef, prepare: prepareLayoutMotion } = useDiscoveryLayoutMotion()
  const [job, setJob] = useState<DiscoverySnapshot | null>(initialSnapshot ?? null)
  const displayedResult = useRef(job)
  useLayoutEffect(() => { displayedResult.current = job }, [job])
  const [jobId, setJobId] = useState<string | null>(incoming?.discoveryJobId ?? null)
  const [busy, setBusy] = useState(!!incoming?.discoveryJobId)
  const [locating, setLocating] = useState(false)
  const [error, setError] = useState('')
  const [restoreAttempt, setRestoreAttempt] = useState(0)
  const [restoreFailed, setRestoreFailed] = useState(false)
  const [requestText, setRequestText] = useState(initialMessage ?? incoming?.discoveryMessage ?? '')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [railControls, setRailControls] = useState<HTMLDivElement | null>(null)
  const [location, setLocation] = useState<Coordinate | undefined>()
  const [locationDetails, setLocationDetails] = useState<DiscoveryLocationDetails | undefined>()
  const [locationError, setLocationError] = useState('')
  const [locationEnabled, setLocationEnabled] = useState(initialSnapshot?.position?.use_location !== false)
  const [detailId, setDetailId] = useState<string | null>(null)
  const [mapFocusId, setMapFocusId] = useState<string | null>(null)
  const [railFocus, setRailFocus] = useState<{ id: string; revision: number }>()
  const [version, setVersion] = useState(0)
  const [selectedIds, setSelectedIds] = useState<string[]>(incoming?.discoverySelectedIds ?? [])
  const selection = useRef<string[]>(incoming?.discoverySelectedIds ?? [])
  function choose(ids: string[]) { selection.current = ids; setSelectedIds(ids) }
  const initialMessages = useMemo(() => {
    const turns = initialSnapshot?.conversation ?? (initialMessage ? [{ role: 'user', content: initialMessage }] : [])
    const restored = turns.map((turn, index) => ({ ...turn, id: `history-${initialSnapshot?.id ?? 'new'}-${index}` }))
    if (initialSnapshot?.reply && restored.at(-1)?.content !== initialSnapshot.reply)
      restored.push({ id: `history-${initialSnapshot.id}-reply`, role: 'assistant', content: initialSnapshot.reply })
    return restored
  }, [initialSnapshot, initialMessage])
  const [messages, setMessages, chatStorageUnavailable] = useSessionMessages(
    archiveHistoryId ? `history:${archiveHistoryId}` : 'discovery', user?.username ?? null, !initializing, initialMessages)
  const currentMessages = useRef(setMessages)
  useLayoutEffect(() => { currentMessages.current = setMessages }, [setMessages])
  const serial = useRef(0), activeId = useRef<string | null>(initialSnapshot?.id ?? null)
  const pendingId = useRef<string | null>(incoming?.discoveryJobId ?? null)
  const pendingMessage = useRef(incoming?.discoveryMessage ?? '')
  const locationAttempt = useRef(0)
  const automaticLocationUsed = useRef(false)
  const explorationPending = useRef(false)
  const locateCurrent = useRef<(message: string, sequence: number) => Promise<void>>(async () => {})
  const transcript = useRef<HTMLDivElement>(null)
  const pinHistoryBottom = useRef(false)
  function toggleHistory() {
    const node = transcript.current
    pinHistoryBottom.current = historyOpen || !!node && node.scrollHeight - node.scrollTop - node.clientHeight < 8
    setHistoryOpen(value => !value)
  }
  useLayoutEffect(() => {
    const node = transcript.current
    if (!node) return
    const followBottom = () => { if (pinHistoryBottom.current) node.scrollTop = node.scrollHeight }
    followBottom()
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { pinHistoryBottom.current = false; return }
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(followBottom)
    observer.observe(node)
    return () => observer.disconnect()
  }, [historyOpen, messages.length])
  useLayoutEffect(() => { if (transcript.current) transcript.current.scrollTop = transcript.current.scrollHeight }, [messages.length])
  const alive = useRef(true)
  const authReady = useRef(!initializing)
  const owner = useRef(user?.username ?? null)
  const ownerKnown = useRef(!initializing)
  const savingHistory = useRef(new Set<string>())
  const historyPending = useRef(false)
  const historyRequest = useRef<{ id: string; promise: Promise<string> } | null>(null)
  function persistHistory(id: string) {
    if (historyRequest.current?.id === id) return historyRequest.current.promise
    const account = owner.current
    historyPending.current = true
    const promise = apiClient.post<{ history_id: string }>(`/discovery/jobs/${id}/history`).then(saved => {
      // Publish the new binding before releasing page_loading. Otherwise a
      // resumed command can capture the previous history ID and be rejected
      // when the queued React update commits between proposal and execution.
      if (owner.current === account) flushSync(() => setJob(current => current?.id === id ? { ...current, history_id: saved.history_id } : current))
      return saved.history_id
    }).finally(() => { historyPending.current = false })
    historyRequest.current = { id, promise }
    return promise
  }
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
    setLocationEnabled(true)
    setJob(null); setJobId(null); setBusy(false); setRequestText(''); setError(''); setRestoreFailed(false); setDetailId(null); setLocation(undefined); setLocationDetails(undefined); setLocationError(''); choose([])
  }, [user?.username, initializing])
  useEffect(() => {
    if (!user || !job || !job.cards.length || !['completed', 'partial'].includes(job.status) || job.history_id || savingHistory.current.has(job.id)) return
    if (job.issues?.some(issue => issue.tool === 'history' && issue.code === 'save_unconfirmed')) return
    const id = job.id
    savingHistory.current.add(id)
    void persistHistory(id).then(async () => {
      await nextFrame()
    }).catch(() => { savingHistory.current.delete(id); historyRequest.current = null })
  }, [user, job])
  const resultAccount = user?.username ?? null
  const resultSessionKey = `roambot.discovery-result.v1:${user ? 'user:' + encodeURIComponent(user.username) : 'guest'}`
  useEffect(() => {
    if (initializing || archiveHistoryId || initialSnapshot || incoming?.discoveryJobId || job || busy) return
    let active = true
    const sequence = serial.current
    async function restore() {
      try {
        const saved = readSavedDiscovery(resultSessionKey, resultAccount !== null)
        const result = await restoreDiscoveryResult(saved, resultAccount !== null)
        if (!result) return
        const { snapshot: restored, message } = result
        if (!active || serial.current !== sequence || !['completed', 'partial'].includes(restored.status)) return
        activeId.current = restored.id
        setJob(restored); setRequestText(message); setLocationEnabled(restored.position?.use_location !== false)
        if (restored.conversation?.length) setMessages(current => current.length ? current : restored.conversation!.map((turn, index) => ({ ...turn, id: `restore-${restored.id}-${index}` })))
        setError(''); setRestoreFailed(false)
      } catch {
        if (active && serial.current === sequence) { setError('上次推荐加载失败'); setRestoreFailed(true) }
      }
    }
    void restore()
    return () => { active = false }
  }, [initializing, archiveHistoryId, initialSnapshot, incoming?.discoveryJobId, job, busy, resultSessionKey, resultAccount, restoreAttempt, setMessages])
  useEffect(() => {
    if (initializing || archiveHistoryId || !job || !['completed', 'partial'].includes(job.status) || !job.cards.length || owner.current !== (user?.username ?? null)) return
    saveDiscoveryReference(resultSessionKey, { id: job.id, history_id: job.history_id, message: requestText }, !!user)
  }, [job, requestText, user, initializing, archiveHistoryId, resultSessionKey])
  const layers = useDetailTransition(detailId, version, setDetailId)
  const selected = job?.cards.find(card => card.place.id === detailId)
  const mapVisible = layers.mapOpen || detailId === mapOverviewId
  const focused = mapVisible ? job?.cards.find(card => card.place.id === mapFocusId) ?? selected ?? job?.cards[0] : selected
  const previousOverview = useRef(false)
  useEffect(() => {
    if (previousOverview.current && !detailId && mapFocusId)
      setRailFocus(previous => ({ id: mapFocusId, revision: (previous?.revision ?? 0) + 1 }))
    previousOverview.current = detailId === mapOverviewId
  }, [detailId, mapFocusId])
  const commands = useRef(assistant)
  const currentLayers = useRef(layers)
  useLayoutEffect(() => { commands.current = assistant; currentLayers.current = layers })
  const queryShown = useRef<string | null>(initialSnapshot?.id ?? null)
  useCommandTarget('discovery', () => ({
    page_loading: historyPending.current,
    discovery_job_id: job?.id, history_id: job?.history_id ?? archiveHistoryId,
    result_version: version, focused_id: focused?.place.id,
    selected_ids: selection.current, layer: mapVisible ? 'map' : detailId ? 'detail' : 'results',
    visible_places: job?.cards.map(card => ({ id: card.place.id, name: card.place.name })) ?? [],
    conversation: messages.slice(-6).map(({ role, content }) => ({ role, content })),
  }), async effect => {
    const args = effect.arguments
    if (effect.tool === 'chat_started') {
      setMessages(current => current.at(-1)?.content === args.message ? current : [...current,
        { id: String(args.requestId), role: 'user', content: String(args.message) }])
    } else if (['chat_reply', 'chat_failed'].includes(effect.tool)) {
      setMessages(current => [...current, { id: String(args.requestId) + '-reply', role: 'assistant',
        content: String(args.reply ?? args.message) }])
    } else if (effect.tool === 'clear_conversation') setMessages([])
    else if (effect.tool === 'close_layer') {
      if (layers.mapOpen) layers.closeMap()
      else if (detailId) layers.close()
      else return false
    } else if (effect.tool === 'open_detail' || effect.tool === 'open_map') {
      const id = String(args.id)
      if (!job?.cards.some(card => card.place.id === id)) throw new Error('该地点已不在当前结果中。')
      if (detailId === mapOverviewId && effect.tool === 'open_map') { setMapFocusId(id); return true }
      if (detailId !== id) {
        if (detailId) throw new Error('请先返回当前详情，再打开其他地点。')
        // The next action needs the committed detail before adding map history.
        // A requestAnimationFrame alone does not finish concurrent React work.
        flushSync(() => layers.open(id))
      }
      if (effect.tool === 'open_map') { setMapFocusId(id); currentLayers.current.openMap() }
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
      document.querySelector<HTMLElement>('.discovery-rail')?.focus({ preventScroll: true })
    } else if (effect.tool === 'start_team_pick' || effect.tool === 'end_team_pick') {
      document.querySelector<HTMLElement>('.discovery-rail')?.focus({ preventScroll: true })
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
        const exploring = !!next.exploration?.mode
        // Exploration is append-only on the server; keep the current usable
        // result until a new batch actually contains new places.
        if (exploring && !next.exploration?.new_count) {
          if (next.status === 'running') { timer = setTimeout(() => void poll(), 650); return }
          pendingId.current = null; explorationPending.current = false
          setBusy(false); setJobId(null)
          if (next.reply) setMessages(current => [...current, { id: next.id, role: 'assistant', content: next.reply }])
          return
        }
        // An accepted search is not a replacement result. Keep the current
        // cards, selection and detail until the next query has usable places.
        if (!next.cards.length && displayedResult.current?.cards.length && !next.request_location) {
          if (next.status === 'running') { timer = setTimeout(() => void poll(), 650); return }
          pendingId.current = null; explorationPending.current = false
          activeId.current = jobId // Follow-ups use the latest query's context.
          setBusy(false); setJobId(null)
          if (next.reply) setMessages(current => [...current, { id: next.id, role: 'assistant', content: next.reply }])
          return
        }
        if (archiveHistoryId && next.intent === 'search') {
          pendingId.current = null // Ownership moves to the new page; do not cancel its job on unmount.
          navigation('/explore', { state: { discoveryJobId: jobId,
            discoveryMessage: exploring ? next.search_request || requestText : pendingMessage.current,
            discoverySelectedIds: exploring ? selection.current : [] }, viewTransition: true })
          return
        }
        // Keep the previous card objects and history layer while intent is unknown.
        if (next.intent !== null) {
          if (next.cards.length) setRestoreFailed(false)
          if (queryShown.current !== jobId) {
            queryShown.current = jobId; activeId.current = jobId
            if (!exploring) setRequestText(pendingMessage.current)
            setDetailId(null)
            choose(exploring ? selection.current.filter(id => next.cards.some(card => card.place.id === id)) : [])
            setVersion(value => value + 1)
          }
          setJob(next)
        }
        if (next.status !== 'running') {
          pendingId.current = null
          explorationPending.current = false
          if (exploring) pendingMessage.current = next.search_request || requestText
          setBusy(false)
          if (next.intent === null && !activeId.current) {
            setRequestText(pendingMessage.current)
            // Preserve the owned failed conversation for natural follow-ups.
            activeId.current = jobId
          }
          if (next.request_location && next.status === 'completed' && !next.context.origin) {
            if (!locationEnabled) setLocationError(next.context.max_distance_km != null ? '按距离筛选需设置出发位置' : '选择地区或出发位置')
            else if (next.position?.approximate) setLocationError('定位范围较大 · 选择位置')
            else if (!automaticLocationUsed.current) {
              automaticLocationUsed.current = true
              void locateCurrent.current(pendingMessage.current, serial.current)
            } else setLocationError('重新定位或选择位置')
          } else if (next.reply) setMessages(current => [...current, { id: next.id, role: 'assistant', content: next.reply }])
          return
        }
        timer = setTimeout(() => void poll(), 650)
      } catch (caught) {
        if (!stopped) { explorationPending.current = false; setBusy(false); setError(caught instanceof Error ? caught.message : '查询中断。') }
      }
    }
    void poll()
    return () => { stopped = true; clearTimeout(timer) }
  }, [jobId, busy, archiveHistoryId, navigation, locationEnabled, setMessages, requestText])

  async function send(message: string, point = location, locationContinuation = false, details = locationDetails, usePoint = locationEnabled, exploreMode?: 'batch' | 'area') {
    prepareLayoutMotion()
    const sequence = ++serial.current
    if (!locationContinuation) automaticLocationUsed.current = false
    locationAttempt.current++; setLocating(false)
    const previousId = exploreMode ? displayedResult.current?.id ?? activeId.current : activeId.current
    if (pendingId.current) await apiClient.remove(`/discovery/jobs/${pendingId.current}`).catch(() => undefined)
    if (!alive.current || sequence !== serial.current) return
    setError(''); setJobId(null); setBusy(true)
    pendingMessage.current = message
    try {
      const waitingSince = Date.now()
      while (!authReady.current) {
        if (Date.now() - waitingSince > 10000) throw new Error('登录状态尚未确认，可以稍后重试。')
        await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
      }
      if (!alive.current || sequence !== serial.current) return
      // Identity initialization may resolve to an existing account rather than
      // a guest. Append through that account's committed storage scope.
      if (!locationContinuation) currentMessages.current(current => [...current, { id: crypto.randomUUID(), role: 'user', content: message }])
      const body = {
        message, previous_id: previousId, ...(exploreMode ? { explore_mode: exploreMode } : {}),
        ...(!usePoint ? { use_location: false } : point && !exploreMode ? { location: point, ...(details ? { location_details: details } : {}) } : {}),
        ...(commands.current || exploreMode ? { view: { focused_id: focused?.place.id ?? null,
          selected_ids: selection.current, layer: mapVisible ? 'map' : detailId ? 'detail' : 'results' } } : {}),
        ...(commands.current && messages.length ? { conversation: messages.slice(-6).map(({ role, content }) => ({ role, content })) } : {}),
      }
      let started: { id: string }
      try { started = await apiClient.post<{ id: string }>('/discovery/jobs', body) }
      catch (caught) {
        // An expired source is rejected before any provider call. Rebind only
        // this exact saved history, never substitute another trip's context.
        if (!(caught instanceof ApiError) || caught.status !== 404 || caught.code !== 'discovery_not_found' || !previousId || !user || job?.id !== previousId || !job.history_id) throw caught
        const restored = await apiClient.post<DiscoverySnapshot>(`/discovery/history/${encodeURIComponent(job.history_id)}/restore`)
        if (!alive.current || sequence !== serial.current) return
        activeId.current = restored.id
        setJob(restored)
        started = await apiClient.post<{ id: string }>('/discovery/jobs', { ...body, previous_id: restored.id })
      }
      if (!alive.current || sequence !== serial.current) {
        void apiClient.remove(`/discovery/jobs/${started.id}`).catch(() => undefined); return
      }
      pendingId.current = started.id; setJobId(started.id)
    } catch (caught) {
      if (sequence === serial.current && alive.current) {
        explorationPending.current = false
        setBusy(false); setError(caught instanceof Error ? caught.message : '查询未完成。')
      }
      throw caught
    }
  }

  function explore(mode: 'batch' | 'area') {
    if (explorationPending.current || busy || locating || assistant?.busy || !activeId.current) return
    explorationPending.current = true
    void send(mode === 'batch' ? '换一批' : '看看其他区域', undefined, false, undefined, locationEnabled, mode).catch(() => undefined)
  }

  function cancelSearch() {
    serial.current++; locationAttempt.current++
    const pending = pendingId.current
    pendingId.current = null
    explorationPending.current = false
    setLocating(false); setBusy(false); setJobId(null)
    if (pending) void apiClient.remove(`/discovery/jobs/${pending}`).catch(() => undefined)
  }

  async function locate(message = requestText, sequence = serial.current) {
    const attempt = ++locationAttempt.current
    setError(''); setLocationError(''); setLocating(true)
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }))
      const point = { longitude: position.coords.longitude, latitude: position.coords.latitude, system: 'wgs84' }
      const details: DiscoveryLocationDetails = { source: 'device', replace_origin: true,
        ...(Number.isFinite(position.coords.accuracy) && position.coords.accuracy > 0 ? { accuracy_m: position.coords.accuracy } : {}),
        ...(position.timestamp > 0 ? { captured_at: position.timestamp } : {}) }
      if (!alive.current || sequence !== serial.current || attempt !== locationAttempt.current) return
      setLocation(point); setLocationDetails({ ...details, replace_origin: false }); setLocationEnabled(true)
      if (message) await send(message, point, true, details, true)
    } catch (caught) {
      if (alive.current && sequence === serial.current && attempt === locationAttempt.current) {
        const denied = (caught as GeolocationPositionError | undefined)?.code === 1
        setLocationError(denied ? '未获定位授权 · 选择位置' : '暂未取得位置 · 重试')
      }
    } finally {
      if (alive.current && attempt === locationAttempt.current) setLocating(false)
    }
  }
  useLayoutEffect(() => { locateCurrent.current = locate })

  function selectLocation(place: PlaceSuggestion) {
    if (!place.coordinate) return
    const details: DiscoveryLocationDetails = { source: 'selected', name: place.name }
    setLocation(place.coordinate); setLocationDetails(undefined); setLocationError(''); setLocationEnabled(true)
    const wish = pendingMessage.current || requestText
    if (wish) void send(wish, place.coordinate, true, details, true).catch(() => undefined)
  }

  function useRegionOnly() {
    setLocationEnabled(false); setLocation(undefined); setLocationDetails(undefined); setLocationError('')
    const wish = pendingMessage.current || requestText
    if (wish) void send(wish, undefined, true, undefined, false).catch(() => undefined)
  }

  const chat = <LayerConversation label='继续聊这次出游' focusedPlace={focused?.place.name ?? 'RoamBot'}
    messages={messages} status={busy ? job?.stage ?? '' : ''} busy={busy || !!assistant?.busy} onSend={send} />
  const mapItems = useMemo(() => (job?.cards ?? []).map(card => ({ destination: {
    provider_id: card.place.id, name: card.place.name, city: card.place.city,
    address: card.place.address, coordinate: arrivalCoordinate(card),
  }, card })), [job?.cards])
  const landing = !requestText && !job && !messages.length && !busy && !locating
  const heading = discoveryTitle(requestText, job?.display_title, job?.conversation, job?.context.region)
  return <div ref={workspaceRef} className='discovery-workspace' data-landing={landing} data-home-entry={!!incoming?.homeEntry}>
    <div className='discovery-browse' data-command-scroll tabIndex={0} aria-label='推荐内容'>
    <header className='discovery-intro'>
      <h1 data-long-request={Array.from(heading).length > 22}><span data-discovery-motion>{heading}</span></h1>
      <div className='discovery-context'>
        {!landing && <DiscoveryLocationPill
          position={job?.position} fallback={job?.center_name} locating={locating} error={locationError}
          region={job?.context.region} onRegionOnly={locationEnabled && job?.context.region && !job.context.origin && job.context.max_distance_km == null ? useRegionOnly : undefined}
          onRetry={() => void locate()} onSelect={selectLocation} />}
        {job?.context.region && (job.position?.label || job.center_name) && job.position?.source !== 'region' && <span>{job.context.region}</span>}
        {job?.context.max_distance_km && <span>实际路程 {job.context.max_distance_km} km 内</span>}
        {job?.context.start_date && <span>{job.context.start_date} 至 {job.context.end_date}</span>}
      </div>
    </header>
    <div className='discovery-status' aria-live='polite'>
      {busy && !!job?.cards.length && <p role='status' className='discovery-working-status'><span className='discovery-status-orbit' aria-hidden='true'><i /></span>{job?.stage || '正在理解这次想法…'}</p>}
      {!busy && !locating && !job?.request_location && !job?.cards.length && job?.reply && <p>{job.reply}</p>}
      {error && <p role='alert'>{error}</p>}
      {restoreFailed && !busy && <button className='text-button' type='button' onClick={() => { setError(''); setRestoreFailed(false); setRestoreAttempt(value => value+1) }}>重新加载推荐</button>}
    </div>
    <div className='discovery-results'>
    <DiscoveryWaiting active={busy && !job?.cards.length} stage={job?.stage || '正在理解这次想法…'}
      runId={jobId} notes={job?.id === jobId ? job?.progress_notes : undefined} />
    <DiscoveryRail resetKey={job?.id} focusRequest={railFocus} controlsTarget={railControls} actions={!!job?.cards.length && <>
      <button type='button' className='text-button discovery-explore-button' title='保持当前想法，优先换成已找到但还没展示的地点'
        disabled={busy || locating || !!assistant?.busy} onClick={() => explore('batch')}>换一批</button>
      <button type='button' className='text-button discovery-explore-button' title='保持当前想法，探索其他区域；可能需要重新检索'
        disabled={busy || locating || !!assistant?.busy} onClick={() => explore('area')}>看看其他区域</button>
      <button type='button' className='text-button discovery-explore-button discovery-map-entry' title='在地图上查看本轮全部推荐地点'
        onClick={() => { setMapFocusId(current => job.cards.some(card => card.place.id === current) ? current : job.cards[0].place.id); layers.open(mapOverviewId) }}><Map size={15} aria-hidden='true' />地图</button>
    </>}>
      {job?.cards.map((card, index) => <article key={card.place.id} className='discovery-card glass-panel' data-place-id={card.place.id}>
        <button type='button' className='discovery-card-open' aria-label={`了解${card.place.name}`} onClick={() => layers.open(card.place.id)} />
        <div className='discovery-card-heading'><span className='discovery-experience'>{placeType(card.place.map_type) || card.place.city}</span>
          <div className='discovery-card-heading-actions'><span className='discovery-card-number'>{String(index + 1).padStart(2, '0')}</span>
            <DiscoveryFavoriteControl card={card} source={job.source} compact />
          </div></div>
        <h2>{card.place.name}</h2>
        <p className='discovery-card-city'><MapPin size={13} />{placeArea(card)}</p>
        <DiscoveryCardSummary card={card} />
        <footer>
          <button type='button' className='text-button' aria-pressed={selectedIds.includes(card.place.id)} onClick={() => choose(selection.current.includes(card.place.id)
            ? selection.current.filter(id => id !== card.place.id) : selection.current.length < 3 ? [...selection.current, card.place.id] : selection.current)}>{selectedIds.includes(card.place.id) ? '已选入比较' : '加入比较'}</button>
          <AddToItinerary source={{ source_job_id: job.id, place_id: card.place.id }} />
        </footer>
      </article>)}
    </DiscoveryRail>
    </div>
    {!!selectedIds.length && <div className='discovery-selection glass-panel'>
      <div className='discovery-selection-summary'><strong>已选 {selectedIds.length} 个地点</strong><div className='discovery-selected-names'>
        {job?.cards.filter(c => selectedIds.includes(c.place.id)).map(c => <button className='text-button' type='button' key={c.place.id}
          aria-label={`移出候选：${c.place.name}`} onClick={() => choose(selection.current.filter(id => id !== c.place.id))}><span>{c.place.name}</span><X size={12} /></button>)}
      </div></div>
      <div className='discovery-selection-actions'>
        <button type='button' className='text-button' disabled={selectedIds.length < 2} onClick={() => layers.open(comparisonId)}>查看对比</button>
        <DiscoveryPlanControl names={job?.cards.filter(c => selectedIds.includes(c.place.id)).map(c => c.place.name) ?? []} selectedIds={selectedIds}
          startDate={job?.context.start_date} endDate={job?.context.end_date} disabled={busy}
          getHistoryId={async () => {
            const id = job?.history_id ?? archiveHistoryId
            if (id) return id
            if (!job) throw new Error('请先选择当前推荐的地点。')
            return persistHistory(job.id)
          }} />
      </div>
    </div>}
    </div>
    <div className='discovery-results-toolbar' ref={setRailControls} />
    <div className='discovery-input' data-history-open={historyOpen}>
      {!landing && <>
      {chatStorageUnavailable && <p role='status'>当前浏览器无法保存聊天，刷新前请保留需要的内容。</p>}
      <div className='discovery-conversation studio-conversation' ref={transcript} role='log' aria-label='本次对话记录' tabIndex={0}
        onWheel={() => { pinHistoryBottom.current = false }} onTouchStart={() => { pinHistoryBottom.current = false }}
        onTransitionEnd={event => { if (event.target === event.currentTarget && event.propertyName === 'height') pinHistoryBottom.current = false }}>
        {messages.map((message, index) => <p className={message.role} key={`${message.id}:${index}`}>{message.content}</p>)}
      </div>
      {!!messages.length && <div className='discovery-chat-toolbar'>
        <button type='button' className='text-button' aria-expanded={historyOpen} onClick={toggleHistory}>{historyOpen ? '收起历史对话' : '展开历史对话'}</button>
      </div>}</>}
      <Composer busy={busy || !!assistant?.busy} onSend={send} initialText={incoming?.initialIdea}
        onCancel={busy || locating ? cancelSearch : undefined}
        placeholder={landing ? '想找一片湖边，坐着发会儿呆……' : undefined}
        suggestions={landing ? ['去公园散步', '去湖边走走', '找家书店逛逛'] : undefined} />
      {assistant?.resultLink && <a className='text-button' href={assistant.resultLink} target='_blank' rel='noreferrer'>打开刚生成的链接</a>}
    </div>
    {detailId === comparisonId && <OverlayHost label='地点对比' onClose={layers.close} className='discovery-detail-overlay' panelClassName='discovery-detail glass-panel' accessory={chat}>
      <button className='icon-button discovery-close' aria-label='返回推荐' onClick={layers.close}><X size={20} /></button>
      <h2>地点对比</h2><DiscoveryComparison cards={job?.cards.filter(card => selectedIds.includes(card.place.id)) ?? []} onOpen={layers.open} />
    </OverlayHost>}
    {selected && <OverlayHost label={`${selected.place.name}详情`} onClose={layers.close} className='discovery-detail-overlay' panelClassName='discovery-detail glass-panel' accessory={chat}>
      <button className='icon-button discovery-close' aria-label='返回推荐' onClick={layers.close}><X size={20} /></button>
      <header className='discovery-detail-heading'>
        <div><h2>{selected.place.name}</h2>
          <p className='discovery-detail-area'>{placeArea(selected)}</p>
          {activityLabel(selected) && <p className='discovery-detail-activity'>{activityLabel(selected)}</p>}
          {routeLabel(selected) && <div className='discovery-facts'><RouteFact card={selected} /></div>}
        </div>
        <PlaceTypeArtwork typeName={selected.place.map_type} />
      </header>
      <DiscoveryCardDetails card={selected} />
      <footer className='discovery-detail-actions'><button type='button' className='text-button' data-studio-map-trigger onClick={() => { setMapFocusId(selected.place.id); layers.openMap() }}><AmapLogo />查看位置</button>
        <PlaceGuideLink name={selected.place.name} city={selected.place.city} />
        <DiscoveryFavoriteControl key={`${selected.place.id}:${user?.username ?? 'guest'}`} card={selected} source={job?.source ?? 'live'} /></footer>
    </OverlayHost>}
    {mapVisible && !!mapItems.length && <LocationMapDialog items={mapItems} selectedId={mapFocusId ?? selected?.place.id ?? mapItems[0].destination.provider_id}
      title={detailId === mapOverviewId ? '推荐地图' : '景点位置'}
      renderSelected={item => <DiscoveryMapCard key={item.card.place.id} card={item.card} jobId={job!.id} source={job!.source} />}
      onSelect={item => setMapFocusId(item.destination.provider_id)} onClose={detailId === mapOverviewId ? layers.close : layers.closeMap}>{chat}</LocationMapDialog>}
  </div>
}
