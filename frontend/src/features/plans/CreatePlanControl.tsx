import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'

import { apiClient } from '../../api/client'
import type { LegacyHistoryDetail, TravelPlan } from '../../api/types'
import { AuthDialog } from '../auth/AuthDialog'
import { useAuth } from '../auth/authContext'
import { announcePlanChange, defaultPlanName, planError } from './planPresentation'

type Props = {
  historyId: string | null
  trusted: boolean
  selectedIds: string[]
  city: string
  startDate: string
  endDate: string
  originCount: number
  onRerun: () => Promise<unknown>
  dirty?: boolean
  compact?: boolean
}

export function CreatePlanControl(props: Props) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [authOpen, setAuthOpen] = useState(false)
  const [name, setName] = useState<string | null>(null)
  const planName = name ?? defaultPlanName(props.city, props.startDate, props.endDate)
  const [count, setCount] = useState(String(Math.max(1, props.originCount)))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const outside = useRef(false)
  const titleId = useId()
  const ownershipKey = user && props.historyId ? `${user.username}:${props.historyId}` : ''
  const [verified, setVerified] = useState({ key: '', ids: [] as string[], start: '', end: '' })
  const trusted = props.trusted || (ownershipKey !== '' && verified.key === ownershipKey
    && verified.start === props.startDate && verified.end === props.endDate
    && props.selectedIds.every(id => verified.ids.includes(id)))
  const checking = open && Boolean(ownershipKey) && !props.trusted && verified.key !== ownershipKey
  useEffect(() => {
    if (!open || props.trusted || !ownershipKey || verified.key === ownershipKey) return
    let active = true
    // Session storage deliberately drops ownership. Confirm it with the server after a route return.
    void apiClient.get<{ history: LegacyHistoryDetail }>(`/history/${props.historyId}`).then(({ history }) => {
      if (!active) return
      const valid = history?.id === props.historyId && history.mode === 'recommendation'
        && 'items' in history.result
      setVerified({ key: ownershipKey,
        ids: valid && 'items' in history.result ? history.result.items.map(item => item.destination.provider_id) : [],
        start: valid ? history.request.start_date : '', end: valid ? history.request.end_date : '' })
    }).catch(() => { if (active) setVerified({ key: ownershipKey, ids: [], start: '', end: '' }) })
    return () => { active = false }
  }, [open, props.trusted, props.historyId, ownershipKey, verified.key])
  const exitAnimation = useRef<Animation | null>(null)
  useEffect(() => () => { exitAnimation.current?.cancel() }, [])

  function show() {
    if (props.dirty || props.selectedIds.length < 2 || props.selectedIds.length > 3) return
    if (!user) { setAuthOpen(true); return }
    setOpen(true)
    dialog.current?.showModal()
  }

  function close() {
    if (exitAnimation.current) return
    const element = dialog.current
    const finish = () => {
      exitAnimation.current = null
      element?.classList.remove('is-closing')
      if (!element?.isConnected) return
      element.close()
      setOpen(false)
      setError('')
    }
    if (!element || typeof element.animate !== 'function' || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { finish(); return }
    element.classList.add('is-closing')
    const animation = element.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'none' }],
      { duration: 280, easing: 'cubic-bezier(.22,.75,.18,1)' })
    exitAnimation.current = animation
    void animation.finished.then(finish, () => { exitAnimation.current = null })
  }

  async function run(action: () => Promise<unknown>) {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setError('')
    try { await action() } catch (caught) { setError(planError(caught)) }
    finally { setBusy(false); lock.current = false }
  }

  return <div className='create-plan-control'>
    <div><strong>和同行者一起选</strong><p>保存这几个地点，邀请大家投票。</p></div>
    <button className='primary-button' type='button' disabled={props.dirty || props.selectedIds.length < 2 || props.selectedIds.length > 3} onClick={show}>发起同行计划</button>
    {!props.compact && !props.dirty && props.selectedIds.length < 2 && <small>再选 {2 - props.selectedIds.length} 个地点即可发起</small>}
    {!props.compact && props.dirty && <p className='muted'>条件已修改，请先更新推荐再邀请同行。</p>}
    {createPortal(<AuthDialog open={authOpen} onClose={() => setAuthOpen(false)} onAuthenticated={() => {
      setAuthOpen(false)
      setOpen(true)
      dialog.current?.showModal()
    }} />, document.body)}
    <dialog ref={dialog} className='plan-create-dialog' aria-labelledby={titleId}
      onPointerDown={event => {
        const rect = event.currentTarget.getBoundingClientRect()
        outside.current = event.target === event.currentTarget && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)
      }}
      onPointerUp={event => {
        const rect = event.currentTarget.getBoundingClientRect()
        if (!busy && outside.current && event.target === event.currentTarget && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) close()
        outside.current = false
      }}
      onCancel={event => { event.preventDefault(); if (!busy) close() }} onClose={() => setOpen(false)}>
      {open && <form noValidate onSubmit={(event) => {
        event.preventDefault()
        if (!trusted || !props.historyId || props.dirty || props.selectedIds.length < 2 || props.selectedIds.length > 3) return
        if (!planName.trim()) { setError('请填写计划名称。'); return }
        if (!count.trim() || !Number.isInteger(Number(count)) || Number(count) < 1 || Number(count) > 100) {
          setError('预计同行人数需为 1–100 的整数。'); return
        }
        void run(async () => {
          const response = await apiClient.post<{ plan: TravelPlan }>('/plans', {
            history_id: props.historyId, candidate_ids: props.selectedIds, name: planName.trim(), expected_count: Number(count),
          })
          announcePlanChange()
          navigate(`/plans/${response.plan.id}`)
        })
      }}>
        <p className='eyebrow'>同行决策</p><h2 id={titleId}>创建同行计划</h2>
        {checking ? <p role='status'>正在确认查询…</p> : !trusted || !props.historyId ? <>
          <p>请更新推荐后创建计划。</p>
          <button className='primary-button' type='button' disabled={busy} onClick={() => void run(async () => {
            await props.onRerun()
          })}>{busy ? '正在更新推荐…' : '更新推荐并继续'}</button>
        </> : props.selectedIds.length < 2 ? <>
          <p>候选地点已变化，请重新选择 2–3 个地点。</p>
          <button className='primary-button' type='button' onClick={close}>重新选择地点</button>
        </> : <>
          <p>{props.city} {props.startDate} 至 {props.endDate} · 已选 {props.selectedIds.length} 个候选</p>
          <label className='field'><span>计划名称</span><input value={planName} maxLength={100} required onChange={e => setName(e.target.value)} /></label>
          <label className='field'><span>预计同行人数</span><input type='number' inputMode='numeric' min={1} max={100} required value={count} onChange={e => { setCount(e.target.value.replace(/^0+(?=\d)/, '')); setError('') }} /></label>
          <button className='primary-button' type='submit' disabled={busy || props.dirty || props.selectedIds.length < 2 || props.selectedIds.length > 3}>{busy ? '正在保存…' : '确认创建'}</button>
        </>}
        {error && <p role='alert' className='plan-form-feedback'>{error}</p>}
        <button className='text-button' type='button' disabled={busy} onClick={close}>取消</button>
      </form>}
    </dialog>
  </div>
}
