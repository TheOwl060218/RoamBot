import { useEffect, useId, useRef, useState } from 'react'
import { X } from 'lucide-react'
import type { TravelPlan } from '../../api/types'
import { OverlayHost } from '../studio/OverlayHost'

export type VoteBody = { preferred_id: string; acceptable_ids: string[] }
type Props = { plan: TravelPlan; open: boolean; busy: boolean; error: string; onClose: () => void; onVote: (body: VoteBody) => Promise<boolean> }

export function PlanVotePanel(props: Props) {
  if (!props.plan.me || props.plan.status !== 'voting' || props.plan.ended) return null
  return <VotePanelBody key={props.plan.id} {...props} />
}
function VotePanelBody({ plan, open, busy, error, onClose, onVote }: Props) {
  const [preferred, setPreferred] = useState(plan.me?.preferred_id ?? '')
  const [acceptable, setAcceptable] = useState(plan.me?.acceptable_ids ?? [])
  const [saving, setSaving] = useState(false)
  const [mobile, setMobile] = useState(() => window.matchMedia?.('(max-width: 700px)').matches ?? false)
  useEffect(() => {
    const query = window.matchMedia?.('(max-width: 700px)')
    if (!query) return
    const update = () => setMobile(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  const lock = useRef(false), panel = useRef<HTMLElement>(null), wasOpen = useRef(false)
  const titleId = useId()
  const validIds = new Set(plan.candidates.map(c => c.id)), selected = validIds.has(preferred) ? preferred : ''
  const disabled = busy || saving
  useEffect(() => {
    if (open && !wasOpen.current) panel.current?.querySelector<HTMLInputElement>('input')?.focus({ preventScroll: true })
    wasOpen.current = open
    if (!open) return
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [open, onClose])
  async function submit() {
    if (disabled || !selected || lock.current) return
    lock.current = true
    setSaving(true)
    try {
      const saved = await onVote({ preferred_id: selected, acceptable_ids: acceptable.filter(id => id !== selected && validIds.has(id)) })
      if (saved) onClose()
    } finally { lock.current = false; setSaving(false) }
  }
  const content = <>
      <div className='plan-vote-panel-heading'><h2 id={titleId}>我的投票</h2><button className='icon-button' type='button' aria-label='收起投票面板' onClick={onClose}><X size={18} aria-hidden='true' /></button></div>
      <p className='muted'>选一个首选，也可以接受其他地点。</p>
      {error && <p className='error-banner' aria-live='polite'>{error}</p>}
      <form onSubmit={event => { event.preventDefault(); void submit() }}>
        <fieldset disabled={disabled} className='plan-compact-vote'><legend className='sr-only'>选择首选与可接受地点</legend>
          <div className='plan-vote-columns' aria-hidden='true'><span>候选地点</span><span>首选</span><span>可接受</span></div>
          {plan.candidates.map(candidate => <div className='plan-vote-choice-row' key={candidate.id}><strong>{candidate.snapshot.destination.name}</strong>
            <label><input type='radio' name='preferred' value={candidate.id} checked={selected === candidate.id} aria-label={`首选 ${candidate.snapshot.destination.name}`} onChange={() => setPreferred(candidate.id)} /></label>
            <label><input type='checkbox' checked={selected === candidate.id || acceptable.includes(candidate.id)} disabled={disabled || selected === candidate.id} aria-label={`可接受 ${candidate.snapshot.destination.name}`} onChange={event => setAcceptable(current => event.target.checked ? [...current, candidate.id] : current.filter(id => id !== candidate.id))} /></label>
          </div>)}
        </fieldset>
        <button className='primary-button' type='submit' disabled={disabled || !selected}>{disabled ? '正在保存…' : plan.me?.preferred_id ? '保存修改' : '提交投票'}</button>
      </form>
  </>
  if (mobile) return open ? <OverlayHost label='我的投票' onClose={onClose} panelClassName='plan-vote-workbench-panel plan-mobile-vote'>{content}</OverlayHost> : null
  return <aside className='plan-vote-slot' inert={!open} aria-hidden={!open}>
    <section className='plan-vote-workbench-panel' role='dialog' aria-modal='false' aria-labelledby={titleId} ref={panel}>{content}</section>
  </aside>
}
