import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { TravelPlan } from '../../api/types'
import { apiClient } from '../../api/client'
import { useAuth } from '../auth/authContext'
import { AuthDialog } from '../auth/AuthDialog'
import { OverlayHost } from '../studio/OverlayHost'
import { announcePlanChange, planError } from '../plans/planPresentation'

type Props = { names: string[]; selectedIds: string[]; startDate?: string | null; endDate?: string | null
  disabled: boolean; getHistoryId: () => Promise<string> }

/** Buttons execute the existing business API. Chat is a separate optional entry. */
export function DiscoveryPlanControl(props: Props) {
  const { user } = useAuth(), navigate = useNavigate()
  const [auth, setAuth] = useState(false), [open, setOpen] = useState(false)
  const [name, setName] = useState('一起出游'), [count, setCount] = useState('2')
  const [start, setStart] = useState(''), [end, setEnd] = useState('')
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const lock = useRef(false), selectionAtOpen = useRef<string[]>([])
  const dateText = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
  const today = new Date(), last = new Date(today)
  last.setDate(last.getDate() + 6)
  const firstDate = dateText(today), lastDate = dateText(last)
  function show() {
    selectionAtOpen.current = [...props.selectedIds]
    setStart(props.startDate ?? ''); setEnd(props.endDate ?? props.startDate ?? '')
    setError(''); setOpen(true)
  }
  async function create() {
    if (lock.current) return
    if (props.selectedIds.join('\0') !== selectionAtOpen.current.join('\0')) { setError('地点已变化，请关闭后重新选择。'); return }
    if (!start || !end) { setError('请选择出行日期。'); return }
    if (start < firstDate || end > lastDate) { setError('出行日期请选在未来七天内。'); return }
    if (end < start) { setError('结束日期不能早于出发日期。'); return }
    if (!name.trim() || !Number.isInteger(Number(count)) || Number(count) < 1 || Number(count) > 100) { setError('请填写计划名称和1–100人的同行人数。'); return }
    lock.current = true; setBusy(true); setError('')
    try {
      const history = await props.getHistoryId()
      const { plan } = await apiClient.post<{ plan: TravelPlan }>('/plans', { history_id: history,
        candidate_ids: selectionAtOpen.current, name: name.trim(), expected_count: Number(count), start_date: start, end_date: end })
      announcePlanChange(); navigate(`/plans/${plan.id}`, { viewTransition: true })
    } catch (caught) { setError(planError(caught)) }
    finally { lock.current = false; setBusy(false) }
  }
  return <>
    <button type='button' className='primary-button' disabled={props.disabled || props.selectedIds.length < 2}
      onClick={() => { if (!user) setAuth(true); else show() }}>发起同行计划</button>
    <AuthDialog open={auth} onClose={() => setAuth(false)} onAuthenticated={() => { setAuth(false); show() }} />
    {open && <OverlayHost label='创建同行计划' panelClassName='discovery-plan-dialog glass-panel' onClose={() => { if (!busy) setOpen(false) }}>
      <h2>创建同行计划</h2><p className='muted'>{props.names.join(' / ')}</p>
      <form onSubmit={event => { event.preventDefault(); void create() }}>
        <label className='field'><span>计划名称</span><input value={name} maxLength={100} required onChange={e => setName(e.target.value)} /></label>
        <div className='discovery-plan-dates'>
          <label className='field'><span>出发日期</span><input type='date' required value={start} min={firstDate} max={lastDate} onChange={e => { setStart(e.target.value); if (!end || end < e.target.value) setEnd(e.target.value) }} /></label>
          <label className='field'><span>结束日期</span><input type='date' required value={end} min={start || firstDate} max={lastDate} onChange={e => setEnd(e.target.value)} /></label>
        </div>
        <label className='field'><span>预计同行人数</span><input type='number' inputMode='numeric' min={1} max={100} required value={count} onChange={e => setCount(e.target.value)} /></label>
        {error && <p role='alert' className='error-banner'>{error}</p>}
        <div className='item-actions'><button className='text-button' type='button' disabled={busy} onClick={() => setOpen(false)}>取消</button>
          <button className='primary-button' type='submit' disabled={busy}>{busy ? '正在创建…' : '确认创建'}</button></div>
      </form>
    </OverlayHost>}
  </>
}
