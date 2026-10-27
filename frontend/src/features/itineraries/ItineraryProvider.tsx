import { createContext, useCallback, useContext, useEffect, useRef, useState, type PropsWithChildren } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '../../api/client'
import { useAuth } from '../auth/authContext'
import { OverlayHost } from '../studio/OverlayHost'
import { BUSINESS_CHANGED } from '../commands/commandEvents'
import { itineraryEvent, type Collection, type Itinerary, type Source } from './types'
import '../../styles/itineraries.css'

type Actions = { add: (source: Source) => Promise<void>; busy: boolean }
const Context = createContext<Actions | null>(null)
export function AddToItinerary({ source, label = '加入行程' }: { source: Source; label?: string }) {
  const actions = useContext(Context)
  return <button type='button' className='text-button itinerary-add' disabled={!actions || actions.busy}
    title='加入最近创建的行程，加入后可以更换行程' onClick={() => void actions?.add(source)}>{label}</button>
}

export function ItineraryProvider({ children }: PropsWithChildren) {
  const { user, initializing } = useAuth()
  const account = user?.username ?? 'guest'
  const owner = useRef(account)
  const [loaded, setLoaded] = useState<{ owner: string; data: Collection } | null>(null)
  const collection = loaded?.owner === account ? loaded.data : null
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const [notice, setNotice] = useState<{ owner: string; text: string } | null>(null)
  const message = notice?.owner === account ? notice.text : ''
  const setMessage = useCallback((text: string) => setNotice(text ? { owner: account, text } : null), [account])
  const [added, setAdded] = useState<{ owner: string; itinerary: Itinerary; stop_id: string; added: boolean } | null>(null)
  const [choosing, setChoosing] = useState(false)
  const [pending, setPending] = useState<{ owner: string; source: Source } | null>(null)
  const [name, setName] = useState('新的出游行程')
  const reload = useCallback(async () => {
    const value = await apiClient.get<Collection>('/itineraries')
    if (owner.current === account) setLoaded({ owner: account, data: value })
    return value
  }, [account])
  useEffect(() => { owner.current = account }, [account])
  useEffect(() => {
    if (initializing) return
    let active = true
    void reload().catch(() => { if (active) setMessage('行程暂时加载失败，可在行程中心重试。') })
    const changed = () => { void reload().catch(() => undefined) }
    window.addEventListener(itineraryEvent, changed); window.addEventListener(BUSINESS_CHANGED, changed)
    return () => { active = false; window.removeEventListener(itineraryEvent, changed); window.removeEventListener(BUSINESS_CHANGED, changed) }
  }, [initializing, reload, setMessage])
  useEffect(() => {
    if ((!added && !message) || choosing || busy) return
    const timer = window.setTimeout(() => { setAdded(null); setMessage('') }, 10000)
    return () => window.clearTimeout(timer)
  }, [added, message, setMessage, choosing, busy])

  async function insert(id: string, source: Source) {
    const value = await apiClient.post<{ itinerary: Itinerary; stop_id: string; added: boolean }>(`/itineraries/${id}/stops`, source)
    if (owner.current !== account) return
    setAdded({ owner: account, ...value }); setMessage(''); setChoosing(false)
    await reload()
  }
  async function add(source: Source) {
    if (lock.current || initializing) return
    lock.current = true; setBusy(true); setMessage('')
    try {
      const data = collection ?? await reload()
      const target = data.itineraries[0]
      if (!target) { setPending({ owner: account, source }); return }
      await insert(target.id, source)
    } catch (error) { if (owner.current === account) setMessage(error instanceof Error ? error.message : '加入未完成。') }
    finally { lock.current = false; setBusy(false) }
  }
  async function create() {
    if (lock.current || !pending || pending.owner !== account) return
    lock.current = true; setBusy(true)
    try {
      const data = await apiClient.post<{ itinerary: Itinerary }>('/itineraries', { name })
      await insert(data.itinerary.id, pending.source)
      if (owner.current === account) setPending(null)
    } catch (error) { if (owner.current === account) setMessage(error instanceof Error ? error.message : '创建未完成。') }
    finally { lock.current = false; setBusy(false) }
  }
  async function transfer(target: string) {
    if (lock.current || !added || added.owner !== account || !added.added) return
    lock.current = true; setBusy(true)
    try {
      const result = await apiClient.post<{ itinerary: Itinerary }>(`/itineraries/${added.itinerary.id}/stops/${added.stop_id}/move`,
        { version: added.itinerary.version, target_id: target })
      if (owner.current === account) { setAdded(null); setChoosing(false); setMessage(`已移到「${result.itinerary.name}」`) }
      await reload()
    } catch (error) { if (owner.current === account) setMessage(error instanceof Error ? error.message : '更换未完成。') }
    finally { lock.current = false; setBusy(false) }
  }
  const visibleAdded = added?.owner === account ? added : null
  return <Context.Provider value={{ add, busy }}>
    {children}
    {(visibleAdded || message) && !choosing && !pending && <div className='itinerary-toast' role='status'>
      {visibleAdded ? <><span>{visibleAdded.added ? '已加入' : '已在'}「{visibleAdded.itinerary.name}」</span>
        {visibleAdded.added && <button className='text-button' type='button' onClick={() => setChoosing(true)}>更换行程</button>}
        <Link className='text-button' to={`/itineraries/${visibleAdded.itinerary.id}`}>查看</Link></> : message}
      <button type='button' className='text-button' aria-label='关闭行程提示' onClick={() => { setAdded(null); setMessage('') }}>×</button>
    </div>}
    {pending?.owner === account && <OverlayHost label='创建行程' onClose={() => { if (!busy) setPending(null) }} panelClassName='itinerary-dialog glass-panel'>
      <h2>先创建一个行程</h2><form onSubmit={e => { e.preventDefault(); void create() }}>
        <label className='field'>行程名称<input autoFocus value={name} onChange={e => setName(e.target.value)} maxLength={100} required /></label>
        {message && <p role='alert'>{message}</p>}<div className='item-actions'>
          <button type='button' className='text-button' disabled={busy} onClick={() => setPending(null)}>取消</button>
          <button className='primary-button' disabled={busy}>{busy ? '正在加入…' : '创建并加入'}</button></div>
      </form>
    </OverlayHost>}
    {choosing && visibleAdded && <OverlayHost label='更换行程' onClose={() => { if (!busy) setChoosing(false) }} panelClassName='itinerary-dialog glass-panel'>
      <h2>把刚加入的地点移到</h2><div className='itinerary-picker'>
        {collection?.itineraries.filter(v => v.id !== visibleAdded.itinerary.id).map(v => <button className='text-button' type='button' key={v.id} disabled={busy} onClick={() => void transfer(v.id)}>{v.name}<small>{v.stops.length} 个地点</small></button>)}
      </div>
      {collection?.itineraries.length === 1 && <p>目前只有一个行程。可到行程中心创建更多。</p>}
      {message && <p role='alert'>{message}</p>}<button className='text-button' type='button' disabled={busy} onClick={() => setChoosing(false)}>关闭</button>
    </OverlayHost>}
  </Context.Provider>
}
