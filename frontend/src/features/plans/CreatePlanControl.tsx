import { useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'

import { apiClient } from '../../api/client'
import type { TravelPlan } from '../../api/types'
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
}

export function CreatePlanControl(props: Props) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [authOpen, setAuthOpen] = useState(false)
  const [name, setName] = useState(() => defaultPlanName(props.city, props.startDate, props.endDate))
  const [count, setCount] = useState(props.originCount)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  function show() {
    if (!user) { setAuthOpen(true); return }
    setOpen(true)
    dialog.current?.showModal()
  }

  function close() {
    dialog.current?.close()
    setOpen(false)
    setError('')
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
    <button className='icon-text-button' type='button' onClick={show}>创建同行计划</button>
    {createPortal(<AuthDialog open={authOpen} onClose={() => setAuthOpen(false)} onAuthenticated={() => {
      setAuthOpen(false)
      setOpen(true)
      dialog.current?.showModal()
    }} />, document.body)}
    <dialog ref={dialog} className='plan-create-dialog' aria-labelledby={titleId}
      onCancel={() => setOpen(false)} onClose={() => setOpen(false)}>
      {open && <form onSubmit={(event) => {
        event.preventDefault()
        void run(async () => {
          const response = await apiClient.post<{ plan: TravelPlan }>('/plans', {
            history_id: props.historyId, candidate_ids: props.selectedIds, name, expected_count: count,
          })
          announcePlanChange()
          navigate(`/plans/${response.plan.id}`)
        })
      }}>
        <p className='eyebrow'>同行决策</p><h2 id={titleId}>创建同行计划</h2>
        {!props.trusted || !props.historyId ? <>
          <p>更新一下推荐，就能把这些地点保存成同行计划。</p>
          <p className='muted'>会沿用你刚才的出行条件。如果地点有变化，请再选一次。现在只更新推荐，不会直接创建计划。</p>
          <button className='primary-button' type='button' disabled={busy} onClick={() => void run(async () => {
            await props.onRerun()
            close()
          })}>{busy ? '正在更新推荐…' : '更新推荐'}</button>
        </> : <>
          <p>{props.city} {props.startDate} 至 {props.endDate} · 已选 {props.selectedIds.length} 个候选</p>
          <label className='field'><span>计划名称</span><input value={name} maxLength={100} required onChange={e => setName(e.target.value)} /></label>
          <label className='field'><span>预计同行人数</span><input type='number' min={1} max={100} required value={count} onChange={e => setCount(Number(e.target.value))} /></label>
          <p className='muted'>人数用于提示进度，不限制同行者加入。邀请页不会公开出发地和坐标。</p>
          <button className='primary-button' type='submit' disabled={busy || props.selectedIds.length < 2}>{busy ? '正在保存…' : '确认创建'}</button>
        </>}
        {error && <p role='alert' className='field-error'>{error}</p>}
        <button className='text-button' type='button' disabled={busy} onClick={close}>取消</button>
      </form>}
    </dialog>
  </div>
}
