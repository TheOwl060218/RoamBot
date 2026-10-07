import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CalendarDays, Check, Copy, Pencil, Users, Vote } from 'lucide-react'

import { apiClient } from '../../api/client'
import type { TravelPlan } from '../../api/types'
import { ConfirmDialog } from '../../app/ConfirmDialog'
import { announcePlanChange, compactDates, planError, planProgress, planStatus } from './planPresentation'
import { usePlanClock } from './usePlanClock'
import { PlanComparison } from './PlanComparison'
import { PlanVotePanel, type VoteBody } from './PlanVotePanel'

type Envelope = { plan: TravelPlan; anonymous_csrf?: string | null }

function usePlan(path: string) {
  const [loaded, setLoaded] = useState<{ path: string; data: Envelope } | null>(null)
  const [failure, setFailure] = useState<{ path: string; message: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  useEffect(() => {
    let active = true
    void apiClient.get<Envelope>(path).then(response => { if (active) setLoaded({ path, data: response }) })
      .catch(caught => { if (active) setFailure({ path, message: planError(caught) }) })
    return () => { active = false }
  }, [path])
  async function act(action: () => Promise<Envelope | void>) {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setFailure(null)
    try {
      const response = await action()
      if (response) setLoaded(current => ({ path, data: { ...(current?.path === path ? current.data : null), ...response } }))
      announcePlanChange()
    } catch (caught) { setFailure({ path, message: planError(caught) }) }
    finally { lock.current = false; setBusy(false) }
  }
  return { data: loaded?.path === path ? loaded.data : null, error: failure?.path === path ? failure.message : '', busy, act }
}

export function PlansPage() {
  const [plans, setPlans] = useState<TravelPlan[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    void apiClient.get<{ plans: TravelPlan[] }>('/plans').then(r => { if (active) setPlans(r.plans) })
      .catch(e => { if (active) setError(planError(e)) })
    return () => { active = false }
  }, [])
  return <section className='plan-page'>
    <header className='plan-page-heading'><div><p className='eyebrow'>从候选到共同决定</p><h1>计划中心</h1><p>你发起的计划会一直保存在这个账户中。</p></div><Link className='icon-text-button' to='/'>开始一次推荐</Link></header>
    {error && <p role='alert' className='error-banner'>{error}</p>}
    {!plans && !error && <p className='loading-state'>正在加载计划…</p>}
    {plans && <>
      <PlanCollection plans={plans.filter(p => !p.ended).sort((a, b) => ({ closed: 0, voting: 1, decided: 2 }[a.status] - { closed: 0, voting: 1, decided: 2 }[b.status]))} />
      <PlanCollection plans={plans.filter(p => p.ended)} archived />
    </>}
  </section>
}

function PlanCollection({ plans, archived = false }: { plans: TravelPlan[]; archived?: boolean }) {
  const rail = useRef<HTMLDivElement>(null)
  const label = archived ? '已结束的出行' : '进行中的计划'
  function scroll(direction: number) {
    if (!rail.current) return
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    rail.current.scrollBy({ left: direction * Math.max(280, rail.current.clientWidth * .8), behavior: reduced ? 'instant' : 'smooth' })
  }
  return <section className='plan-section' aria-label={label}>
    <div className='plan-collection-heading'><h2>{label}</h2>
      {!archived && plans.length > 3 && <div className='plan-rail-controls'>
        <button className='icon-text-button' type='button' aria-label='向左查看计划' onClick={() => scroll(-1)}><ArrowLeft size={18} aria-hidden='true' /></button>
        <button className='icon-text-button' type='button' aria-label='向右查看计划' onClick={() => scroll(1)}><ArrowRight size={18} aria-hidden='true' /></button>
      </div>}
    </div>
    {plans.length === 0 ? <p className='plan-empty-line'>{archived ? '结束后的计划会留在这里' : '还没有进行中的计划'}</p>
      : <div ref={rail} role='group' aria-label='出行计划卡片'
        className={archived ? 'plan-grid' : `plan-workbench-cards${plans.length > 3 ? ' plan-card-rail' : ''}`}>
        {plans.map(p => <Link className='plan-card plan-list-card' to={`/plans/${p.id}`} key={p.id}>
          <div className='plan-list-topline'><span className={`plan-badge ${p.status}`}>{planStatus(p)}</span>
            <span className='plan-list-date'>{compactDates(p.start_date, p.end_date)}</span></div>
          <h3>{p.name}</h3>
          <p className='muted'>{p.city} · {p.candidates.length} 个候选</p>
          <p className='plan-list-candidates'>{p.status === 'decided'
            ? `目的地：${p.candidates.find(c => c.id === p.final_candidate_id)?.snapshot.destination.name ?? '待确认'}`
            : p.candidates.map(c => c.snapshot.destination.name).join(' / ')}</p>
          <p className='plan-meta'><Users size={16} aria-hidden='true' />{planProgress(p)}</p>
          <span className='plan-card-action'>{archived ? '查看出行记录' : p.status === 'closed' ? '决定目的地' : p.status === 'decided' ? '查看出行安排' : '查看投票'}<ArrowRight size={16} aria-hidden='true' /></span>
        </Link>)}
      </div>}
  </section>
}

function PlanHeader({ plan, owner }: { plan: TravelPlan; owner: boolean }) {
  const joined = plan.summary?.joined_count ?? plan.participants?.length
  const voted = plan.summary?.voted_count ?? plan.participants?.filter(member => member.voted).length
  const known = joined !== undefined && voted !== undefined
  const remaining = known ? Math.max(0, joined - voted) : 0
  const destination = plan.candidates.find(candidate => candidate.id === plan.final_candidate_id)?.snapshot.destination.name
  let progress = known ? `${voted}/${joined} 人已投票` : plan.me ? '先投票，再查看进展' : '加入计划，一起选目的地'
  let next = known
    ? remaining ? `还有 ${remaining} 位同行者未投票，可先比较候选。` : joined ? '已加入的同行者都已投票。' : '邀请同行者加入，一起选择目的地。'
    : '投票后可查看大家的进展，不会提前公开选择。'
  if (plan.ended) { progress = '出行已结束'; next = destination ? `最终目的地：${destination}，计划已留档。` : '计划已留档，可回顾候选与投票记录。' }
  else if (plan.status === 'decided') { progress = destination ?? '目的地已确定'; next = '出行前可以按需再检查一次天气。' }
  else if (plan.status === 'closed') { progress = owner ? '等待你确定目的地' : '等待发起者确定目的地'; next = '投票已结束，可结合同行者的选择和天气查看候选。' }
  return <header className='plan-page-heading plan-workbench-heading'>
    <div className='plan-heading-info'><h1>{plan.name}</h1><p className='plan-meta'><CalendarDays size={17} aria-hidden='true' />{compactDates(plan.start_date, plan.end_date)}<span className={`plan-badge ${plan.status}`}>{planStatus(plan)}</span><span className='plan-candidate-total'>{plan.candidates.length} 个候选</span></p></div>
    <section className='plan-heading-progress' aria-label='同行进展'><span className='plan-heading-progress-label'><Users size={16} aria-hidden='true' />同行进展</span><strong>{progress}</strong><p>{next}</p></section>
  </header>
}

function PlanWorkbench({ plan, busy, error, onVote, management, ownerActions, comparisonActions, decisionAction }: {
  plan: TravelPlan; busy: boolean; error: string; onVote: (body: VoteBody) => Promise<boolean>
  management?: ReactNode; ownerActions?: ReactNode; comparisonActions?: ReactNode
  decisionAction?: React.ComponentProps<typeof PlanComparison>['decisionAction']
}) {
  const [open, setOpen] = useState(false), [started, setStarted] = useState(false), [managing, setManaging] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const canVote = plan.status === 'voting' && !plan.ended && Boolean(plan.me), visible = open && canVote
  const close = () => { setOpen(false); trigger.current?.focus({ preventScroll: true }) }
  return <>
    <PlanHeader plan={plan} owner={Boolean(management)} />
    <div className='plan-comparison-toolbar plan-workbench-toolbar'><div><h2>比较候选地点</h2><p className='muted'>同时看同一天，更容易比较差异。</p></div><div className='plan-workbench-actions'>
      {management && <button className='icon-text-button' type='button' aria-expanded={managing} onClick={() => { if (!managing) setOpen(false); setManaging(value => !value) }}>{managing ? '收起管理' : '管理计划'}</button>}
      {ownerActions}
      {!management && plan.me && <span className='plan-badge plan-member-badge'>{plan.me.nickname} · 已加入</span>}
      {canVote && <button className='icon-text-button' type='button' aria-expanded={visible} ref={trigger} onClick={() => { if (visible) close(); else { setStarted(true); setOpen(true) } }}><Vote size={17} aria-hidden='true' />{visible ? '收起投票' : plan.me?.preferred_id ? '修改投票' : started ? '继续投票' : '去投票'}</button>}
    </div></div>
    {managing && management}
    <div className={`plan-decision-workspace${visible ? ' voting' : ''}`}>
      <div className='plan-comparison-region'><PlanComparison plan={plan} hideHeading decisionAction={decisionAction} toolbarActions={comparisonActions} /><VoteSummary plan={plan} /></div>
      <PlanVotePanel plan={plan} open={visible} busy={busy} error={error} onClose={close} onVote={onVote} />
    </div>
  </>
}

function VoteSummary({ plan }: { plan: TravelPlan }) {
  const summary = plan.summary
  if (!summary) return <p className='plan-empty'>先提交自己的投票，再查看当前结果，避免受到他人选择影响。</p>
  return <section className='plan-card'><div className='plan-card-heading'><h2>{plan.status === 'decided' ? '决定时的投票结果' : '当前投票结果'}</h2><span className='plan-badge'>{planProgress(plan)}</span></div>
    {!summary.complete && <p className='muted'>当前结果：尚未达到预计人数，不代表最终共识。</p>}
    <div className='plan-tallies'>{summary.candidates.map(c => <div className='plan-tally' key={c.id}><strong>{plan.candidates.find(item => item.id === c.id)?.snapshot.destination.name}</strong><div><span>{c.preferred_count} 首选</span><span>{c.acceptable_count} 人可接受</span></div>{c.all_accept && <small>所有已投票成员均可接受</small>}</div>)}</div>
    <p className='muted'>票数不影响原推荐评分。并列时由发起者决定。</p>
  </section>
}

export function PlanDetailPage() {
  const now = usePlanClock()
  const { planId = '' } = useParams()
  const path = `/plans/${planId}`
  const { data, error, busy, act } = usePlan(path)
  const [inviteUrl, setInviteUrl] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState(false)
  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), 2000)
    return () => window.clearTimeout(timer)
  }, [notice])
  const [confirm, setConfirm] = useState<{ title: string; message: string; label: string; action: () => Promise<Envelope | void> } | null>(null)
  const navigate = useNavigate()
  const plan = data?.plan
  async function rotate() {
    const result = await apiClient.post<{ url: string }>(`${path}/invite/rotate`)
    setInviteUrl(new URL(result.url, window.location.origin).href)
    setNotice('邀请已生成。复制后发给同行者即可；换新会使旧链接失效。')
    return apiClient.get<Envelope>(path)
  }
  async function share() {
    try {
      if (window.matchMedia('(max-width: 600px)').matches && navigator.share) {
        await navigator.share({ title: plan?.name, url: inviteUrl })
      } else {
        await navigator.clipboard.writeText(inviteUrl)
      }
      setNotice('邀请链接已分享或复制。')
    } catch { setNotice('未完成分享，可在下方选中链接手动复制。') }
  }
  function rename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    void act(async () => {
      const result = await apiClient.patch<Envelope>(path, { name: fields.get('name'), expected_count: Number(fields.get('expected_count')) })
      setEditing(false)
      setNotice('计划信息已保存。')
      return result
    })
  }
  return <section className='plan-page plan-detail-page'>
    <Link to='/plans' className='plan-back'><ArrowLeft size={16} aria-hidden='true' />计划中心</Link>
    {error && <p role='alert' className='error-banner'>{error}</p>}
    {!plan && !error && <p>正在加载计划…</p>}
    {plan && <PlanWorkbench key={plan.id} plan={plan} busy={busy} error={error}
      management={<section className='plan-card plan-management-workbench' aria-label='计划管理'>
        <section className='plan-management-info'><div className='plan-card-heading'><h2>计划信息</h2><button className='icon-text-button plan-edit-toggle' type='button' aria-label={editing ? '收起计划编辑' : '编辑计划信息'} aria-expanded={editing} onClick={() => setEditing(current => !current)}><Pencil size={15} aria-hidden='true' />{editing ? '收起' : '编辑'}</button></div>
          {!editing && <div className='plan-management-overview'><strong>{plan.name}</strong><span><Users size={16} aria-hidden='true' />预计 {plan.expected_count} 人同行</span></div>}
          {editing && <form id='plan-rename-form' onSubmit={rename} className='plan-edit-form' key={plan.updated_at}>
            <label className='field'><span>计划名称</span><input name='name' defaultValue={plan.name} maxLength={100} required /></label>
            <label className='field'><span>预计同行人数</span><input name='expected_count' type='number' min={1} max={100} defaultValue={plan.expected_count} required /></label>

          </form>}

          <div className='plan-management-action-row'>{editing && <button form='plan-rename-form' type='submit' className='icon-text-button' disabled={busy}>保存信息</button>}</div>
        </section><section className='plan-management-invite'><h2>邀请同行者</h2>
          <div className='plan-management-action-row'><button className='icon-text-button' type='button' disabled={busy} onClick={() => {
            if (plan.invite_active) setConfirm({ title: '换新邀请链接？', message: '旧链接将立即失效。已加入成员与投票会保留。', label: '确认换新', action: rotate })
            else void act(rotate)
          }}>{plan.invite_active ? '换新邀请' : '生成邀请'}</button>
          {plan.invite_active && <button className='text-button' type='button' disabled={busy} onClick={() => setConfirm({ title: '撤销邀请？', message: '现有链接将无法继续访问此计划。', label: '确认撤销', action: async () => { await apiClient.delete(`${path}/invite`); setInviteUrl(''); return apiClient.get<Envelope>(path) } })}>撤销邀请</button>}</div>
          {inviteUrl && <div className='plan-link-copy'><label className='field'><span>邀请链接</span><input readOnly value={inviteUrl} onFocus={e => e.target.select()} /></label><button type='button' className='icon-text-button' onClick={() => void share()}><Copy size={16} aria-hidden='true' />分享 / 复制邀请</button></div>}
          <p className='muted'>只分享城市、日期与候选信息；不会公开出发地和坐标。同行者清除 Cookie 后需重新加入。</p>
        </section>
        <section className='plan-management-members'><h2>同行者</h2><ul className='plan-participants'>{plan.participants?.map(p => <li key={p.id}><span>{p.nickname} {p.role === 'owner' ? '（发起者）' : ''}</span><span>{p.voted ? '已投票' : '未投票'}</span>{p.role === 'guest' && <button className='text-button' type='button' disabled={busy} onClick={() => setConfirm({ title: `移除 ${p.nickname}？`, message: '该成员的投票也会删除。', label: '确认移除', action: async () => { await apiClient.delete(`${path}/participants/${p.id}`); return apiClient.get<Envelope>(path) } })}>移除</button>}</li>)}</ul><div className='plan-management-action-row'><button className='text-button plan-delete' disabled={busy} type='button' onClick={() => setConfirm({ title: '永久删除计划？', message: '候选、投票、成员、邀请与天气记录会一并删除，无法恢复。', label: '永久删除', action: async () => { await apiClient.delete(path); navigate('/plans') } })}>删除计划</button></div></section>

      </section>}
      ownerActions={<>        {plan.status === 'voting' && !plan.ended && <button className='icon-text-button' type='button' disabled={busy} onClick={() => setConfirm({ title: '结束本轮投票？', message: '已有投票会保留，同行者将不能再投票或改票。你可以稍后决定目的地，也可以重新开放投票。', label: '确认结束投票', action: () => apiClient.put<Envelope>(`${path}/voting-close`) })}>结束投票</button>}
        {plan.status === 'closed' && !plan.ended && <p className='plan-privacy-note'>投票已结束，等待你决定目的地。已有投票已保留。</p>}
        {plan.status !== 'voting' && !plan.ended && <button className='icon-text-button' type='button' disabled={busy} onClick={() => setConfirm({ title: '重新开放投票？', message: '保留成员与投票，清除最终目的地。', label: '确认重新开放', action: () => apiClient.remove<Envelope>(`${path}/decision`) })}>重新开放投票</button>}</>}
      comparisonActions={<div className='plan-check-controls'><button className='icon-text-button' type='button' disabled={busy || plan.ended || Boolean(plan.next_weather_check_at && Date.parse(plan.next_weather_check_at) > now)} onClick={() => void act(() => apiClient.post<Envelope>(`${path}/weather-checks`))}>检查天气</button><small className='muted'>{plan.next_weather_check_at ? `下次可检查：${new Date(plan.next_weather_check_at).toLocaleString()}` : '按需检查，不会自动更新'}</small></div>}
      decisionAction={c => plan.status !== 'decided' && !plan.ended && <button className='icon-text-button plan-decide' disabled={busy} type='button' onClick={() => setConfirm({ title: '确定最终目的地？', message: `决定前往${c.snapshot.destination.name}后，同行者投票将关闭。你仍可重新开放。`, label: '确认决定', action: () => apiClient.put<Envelope>(`${path}/decision`, { candidate_id: c.id }) })} aria-label={`确定${c.snapshot.destination.name}`}>选为目的地</button>}
      onVote={async body => {
        let saved = false
        await act(async () => { const result = await apiClient.put<Envelope>(`${path}/vote`, body); saved = true; return result })
        return saved
      }} />}
    {notice && createPortal(<div className='plan-feedback-bubble' role='status' aria-atomic='true'><Check size={18} aria-hidden='true' /><span>{notice}</span></div>, document.body)}
    <ConfirmDialog open={Boolean(confirm)} title={confirm?.title ?? ''} message={confirm?.message ?? ''} confirmLabel={confirm?.label ?? ''} onCancel={() => setConfirm(null)} onConfirm={() => { const action = confirm?.action; setConfirm(null); if (action) void act(action) }} />
  </section>
}

export function JoinPlanPage() {
  const { inviteToken = '' } = useParams()
  const path = `/public/plans/${inviteToken}`
  const { data, error, busy, act } = usePlan(path)
  const [nickname, setNickname] = useState('')
  const plan = data?.plan
  return <section className='plan-page plan-invite-page'>
    {error && <p role='alert' className='error-banner'>{error}</p>}
    {!plan && !error && <p>正在打开同行邀请…</p>}
    {plan && <>
      <p className='plan-privacy-note'>同行者仅能查看候选公开信息，不会看到任何人的出发地址。</p>
      {plan.status === 'voting' && !plan.ended && !plan.me && <form className='plan-card' onSubmit={e => { e.preventDefault(); void act(() => apiClient.post<Envelope>(`${path}/join`, { nickname })) }}>
        <h2>加入这次出行</h2><label className='field'><span>临时昵称</span><input required maxLength={32} value={nickname} onChange={e => setNickname(e.target.value)} autoComplete='nickname' /></label>
        <p className='muted'>请保留当前浏览器 Cookie，以便回来修改投票。换浏览器或清除 Cookie 后无法找回此临时身份。</p>
        <button className='primary-button' disabled={busy} type='submit'>加入计划</button>
      </form>}
      {plan.status === 'closed' && !plan.ended && <p className='plan-privacy-note'>投票已结束，等待发起者决定目的地。你仍可查看已有投票结果。</p>}
      {plan.status === 'decided' && <p className='plan-decision-banner'>发起者已确定目的地：{plan.candidates.find(c => c.id === plan.final_candidate_id)?.snapshot.destination.name}。投票已关闭。</p>}
      <PlanWorkbench key={plan.id} plan={plan} busy={busy} error={error} onVote={async body => {
        let saved = false
        await act(async () => { const result = await apiClient.put<Envelope>(`${path}/vote`, body, { 'X-Plan-CSRF': data?.anonymous_csrf ?? '' }); saved = true; return result })
        return saved
      }} />
    </>}
  </section>
}
