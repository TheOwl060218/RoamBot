import { useContext, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { apiClient, ApiError } from '../../api/client'
import { requestAccountDialog } from '../../app/accountDialog'
import { ConfirmDialog } from '../../app/ConfirmDialog'
import { announcePlanChange } from '../plans/planPresentation'
import { BusinessAssistantContext } from './commandContext'
import { CommandBridge, contextFingerprint, type CommandContext, type CommandEffect } from './commandBridge'
import { BUSINESS_CHANGED } from './commandEvents'
import { LayerConversation } from '../studio/LayerConversation'
import { focusConversation, usable } from './chatFocus'
import { AuthContext } from '../auth/authContext'

type Proposal = { request_id: string; proposal: string; question: string | null;
  actions: { tool: string; arguments: Record<string, unknown> }[]; requires_confirmation: boolean }
type Step = { tool: string; status: string; result: Record<string, unknown> }
type Execution = { status: 'completed' | 'failed' | 'uncertain' | 'awaiting_input'; steps: Step[];
  error?: { code: string; message: string }; question?: string | null }
type Pending = { proposal: Proposal; fingerprint: string; owner: string | null }
type Attempt = { message: string; requestId: string; context: CommandContext; fingerprint: string;
  owner: string | null; saved?: Pending; confirmed: boolean }
const labels: Record<string, string> = {
  favorite_place: '收藏地点', remove_favorite: '取消收藏', create_plan_from_selection: '创建同行计划',
  rotate_invite: '生成或换新邀请', revoke_invite: '撤销邀请', update_plan: '修改计划',
  delete_plan: '删除计划', remove_participant: '移除成员', submit_vote: '提交投票',
  close_voting: '结束投票', decide_plan: '确定目的地', reopen_voting: '重新开放投票',
  check_plan_weather: '检查天气', join_plan: '加入同行', create_share: '创建分享',
  revoke_share: '撤销分享', delete_history: '删除历史', clear_history: '清空历史',
  run_recommendation: '查询', update_search_conditions: '修改条件', explain_result: '查看结果解读',
  list_history: '查看历史', list_favorites: '查看收藏', list_plans: '查看计划', logout: '退出登录',
}
const frame = () => new Promise<void>(resolve => requestAnimationFrame(() => resolve()))

export function CommandRoot() {
  const auth = useContext(AuthContext)
  const authReady = useRef(!auth?.initializing)
  useLayoutEffect(() => { authReady.current = !auth?.initializing }, [auth?.initializing])
  const [bridge] = useState(() => new CommandBridge())
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([])
  const [pending, setPending] = useState<Pending | null>(null)
  const [lastLink, setLastLink] = useState('')
  const [confirmationText, setConfirmationText] = useState('')
  const lock = useRef(false)
  const deferred = useRef<string | null>(null)
  const attempt = useRef<Attempt | null>(null)
  const selection = useRef<{ owner: string | null; history: string | null; version: number; ids: string[] } | null>(null)
  const focusFrame = useRef<number | null>(null)
  const mounted = useRef(true)
  const restoreChatFocus = () => {
    if (!mounted.current) return
    if (focusFrame.current !== null) cancelAnimationFrame(focusFrame.current)
    focusFrame.current = requestAnimationFrame(() => { focusFrame.current = null; focusConversation() })
  }
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; if (focusFrame.current !== null) cancelAnimationFrame(focusFrame.current) }
  }, [])
  const navigate = useNavigate()
  const location = useLocation()
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if (!event.altKey || (event.code !== 'Slash' && event.key !== '/') || event.isComposing) return
      event.preventDefault()
      focusConversation()
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [])
  const latest = useRef({ page: location.pathname, lastLink, messages })
  useLayoutEffect(() => { latest.current = { page: location.pathname, lastLink, messages } }, [location.pathname, lastLink, messages])
  const getContext = (): CommandContext => {
    const page = latest.current.page
    const planId = page.match(/^\/plans\/([^/]+)$/)?.[1]
    const invite = page.match(/^\/join\/([^/]+)$/)?.[1]
    const historyId = page.match(/^\/history\/([^/]+)$/)?.[1]
    const cached = selection.current?.owner === owner() ? bridge.previousContext('studio') : undefined
    const background = cached ? { history_id: cached.history_id, selected_ids: cached.selected_ids,
      result_version: cached.result_version, dirty: cached.dirty, assistant_turn: cached.assistant_turn } : {}
    return { ...background, page, conversation: latest.current.messages.slice(-6).map(message => ({
      role: message.role, content: message.content.slice(0, 1000) })), ...(planId ? { plan_id: planId } : {}),
      ...(invite ? { invite_token: invite } : {}), ...(historyId ? { history_id: historyId } : {}),
      ...bridge.context() }
  }
  const owner = () => apiClient.authSession?.user.username ?? null
  function rememberLink(link: string) {
    latest.current = { ...latest.current, lastLink: link }
    setLastLink(link)
  }
  async function globalEffect(effect: CommandEffect) {
    const args = effect.arguments
    const pages: Record<string, string> = { home: '/', recommend: '/recommend', favorites: '/favorites',
      history: '/history', plans: '/plans' }
    if (effect.tool === 'navigate') {
      const path = pages[String(args.page)]
      if (!path) throw new Error('未知的站内页面。')
      navigate(path, { viewTransition: true })
    } else if (effect.tool === 'open_plan' || effect.tool === 'open_history') {
      navigate('/' + (effect.tool === 'open_plan' ? 'plans' : 'history') + '/' +
        encodeURIComponent(String(args.id)), { viewTransition: true })
    } else if (effect.tool === 'open_account') {
      if (latest.current.page === '/') { navigate('/recommend'); await bridge.waitFor('studio') }
      await bridge.waitFor('shell')
      await bridge.perform(effect)
    } else if (effect.tool === 'go_back') {
      if (!await bridge.dispatch({ tool: 'close_layer', arguments: {} })) navigate(-1)
    } else if (effect.tool === 'evaluate_favorite') {
      navigate('/recommend', { state: { evaluationTarget: String(args.name) }, viewTransition: true })
    } else if (effect.tool === 'clear_conversation') {
      setMessages([])
      await bridge.dispatch(effect)
    } else if (effect.tool === 'copy_link') {
      if (!latest.current.lastLink) throw new Error('请先生成邀请或分享链接。')
      await navigator.clipboard.writeText(new URL(latest.current.lastLink, window.location.origin).href)
    } else if (effect.tool === 'open_generated_link') {
      if (!latest.current.lastLink) throw new Error('请先生成邀请或分享链接。')
      navigate(latest.current.lastLink, { viewTransition: true })
    } else if (effect.tool === 'refresh_page') {
      window.dispatchEvent(new Event(BUSINESS_CHANGED))
      announcePlanChange()
    } else if (effect.tool === 'scroll_chat') {
      const records = [...document.querySelectorAll<HTMLElement>('.layer-chat-messages,.studio-conversation')].filter(usable).at(-1)
      if (!records) throw new Error('当前没有可展开的聊天记录。')
      const direction = String(args.direction)
      records.scrollTo({ top: direction === 'top' ? 0 : direction === 'bottom' ? records.scrollHeight :
        records.scrollTop + (direction === 'up' ? -1 : 1) * records.clientHeight * .75,
        behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
    } else if (effect.tool === 'scroll_view') {
      const direction = String(args.direction)
      const horizontal = direction === 'left' || direction === 'right'
      const selectors = horizontal ? '.destination-grid,.plan-comparison-rail,.plan-collection-rail' :
        '[role="dialog"],.location-dialog,.studio-detail-host'
      const elements = [...document.querySelectorAll<HTMLElement>(selectors)].filter(element =>
        usable(element) && (horizontal ? element.scrollWidth > element.clientWidth : element.scrollHeight > element.clientHeight))
      const element = elements.at(-1)
      const behavior = matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
      const viewport = element ?? window
      if (direction === 'top' || direction === 'bottom') viewport.scrollTo({
        top: direction === 'top' ? 0 : element?.scrollHeight ?? document.documentElement.scrollHeight, behavior })
      else viewport.scrollBy({ left: horizontal ? (direction === 'left' ? -1 : 1) * (element?.clientWidth ?? innerWidth) * .75 : 0,
        top: horizontal ? 0 : (direction === 'up' ? -1 : 1) * (element?.clientHeight ?? innerHeight) * .7, behavior })
    } else if (['show_tools', 'show_preferences', 'choose_favorite', 'start_team_pick',
      'edit_condition', 'start_new_query', 'undo_new_query', 'end_team_pick'].includes(effect.tool)) {
      if (latest.current.page !== '/recommend') {
        navigate('/recommend', { viewTransition: true })
        await bridge.waitFor('studio')
      }
      await bridge.perform(effect)
    } else if (effect.tool === 'continue_in_studio') {
      navigate('/recommend')
      await bridge.waitFor('studio')
      // A deferred condition edit is a new task after the target page exists.
      deferred.current = String(args.message)
    } else {
      await bridge.perform(effect)
    }
    await frame()
  }
  function say(message: string) {
    setMessages(current => [...current, { role: 'assistant', content: message }].slice(-24))
  }
  async function perform(saved: Pending, confirmed: boolean) {
    if (saved.fingerprint !== contextFingerprint(getContext()) || saved.owner !== owner())
      throw new Error('页面、条件或选择已变化，请重新发起操作。')
    const result = await apiClient.post<Execution>('/assistant/commands/execute', {
      request_id: saved.proposal.request_id, proposal: saved.proposal.proposal, confirmed,
    })
    const unchanged = saved.fingerprint === contextFingerprint(getContext()) && saved.owner === owner()
    let assistantShown = false
    for (let index = 0; index < result.steps.length; index++) {
      const step = result.steps[index]
      const data = step.result
      const link = typeof data.url === 'string' ? data.url :
        (data.share as { url?: string } | undefined)?.url
      if (link && /^\/(join|share)\//.test(link)) rememberLink(link)
      if (step.tool === 'revoke_invite' || step.tool === 'revoke_share') rememberLink('')
      if (data.auth_changed) await apiClient.me()
      if (!unchanged) continue
      const marker = saved.proposal.proposal + ':' + index
      if (sessionStorage.getItem('roambot.effect.' + marker) === 'done') continue
      if (data.plan) {
        await bridge.dispatch({ tool: 'plan_result', arguments: { plan: data.plan } })
        await frame()
      }
      if (data.assistant) {
        if (latest.current.page !== '/recommend' && step.tool !== 'explain_result') {
          navigate('/recommend', { viewTransition: true }); await bridge.waitFor('studio')
          await bridge.dispatch({ tool: 'chat_started', arguments: {
            requestId: saved.proposal.request_id, message: attempt.current?.message ?? '修改条件' } })
        }
        if (latest.current.page === '/recommend') await bridge.perform({ tool: 'assistant_result', arguments: {
          requestId: saved.proposal.request_id, response: data.assistant } })
        assistantShown = true
        await frame()
      }
      if (data.query) {
        if (latest.current.page !== '/recommend') {
          navigate('/recommend', { viewTransition: true }); await bridge.waitFor('studio')
          await bridge.dispatch({ tool: 'chat_started', arguments: {
            requestId: saved.proposal.request_id, message: attempt.current?.message ?? '查询' } })
        }
        await bridge.perform({ tool: 'query_result', arguments: data })
      }
      const effect = data.effect as CommandEffect | undefined
      if (effect) await globalEffect(effect)
      sessionStorage.setItem('roambot.effect.' + marker, 'done')
    }
    window.dispatchEvent(new Event(BUSINESS_CHANGED))
    announcePlanChange()
    const completed = result.steps.map(s => labels[s.tool] ?? '页面操作').join('、')
    const explanation = result.steps.map(step => typeof step.result.reply === 'string' ? step.result.reply :
      (step.result.assistant as { reply?: string } | undefined)?.reply ?? '').filter(Boolean).join('\n')
    const reply = result.status === 'awaiting_input' ? result.question ?? '请补充未明确的条件。' : result.status === 'completed'
      ? (explanation || (completed ? completed + '已完成。' : result.question ?? '请补充要执行的操作。'))
      : (completed ? completed + '已完成；' : '') + (result.error?.message ?? '后续操作未完成。')
    if (result.status === 'failed' || result.status === 'uncertain') {
      if (attempt.current?.requestId === saved.proposal.request_id && unchanged) {
        const updated = contextFingerprint(getContext())
        attempt.current.fingerprint = updated
        saved.fingerprint = updated
      }
      throw new Error(reply)
    }
    attempt.current = null
    say(unchanged ? reply : reply + ' 当前页面已变化，未覆盖当前内容。')
    if (!assistantShown) await bridge.dispatch({ tool: 'chat_reply', arguments: {
      requestId: saved.proposal.request_id, reply } })
  }
  async function confirm() {
    if (lock.current || !pending) return
    lock.current = true; setBusy(true)
    const saved = pending
    setPending(null)
    if (attempt.current?.requestId === saved.proposal.request_id) attempt.current.confirmed = true
    await bridge.dispatch({ tool: 'chat_started', arguments: {
      requestId: saved.proposal.request_id, message: '确认执行' } })
    try { await perform(saved, true) }
    catch (error) { say(error instanceof Error ? error.message : '操作未完成。') }
    finally { lock.current = false; setBusy(false); restoreChatFocus() }
  }
  async function send(message: string) {
    if (lock.current) throw new Error('当前操作仍在执行，请稍后发送。')
    if (!message.trim()) return
    if (pending && /^(确认|确定|执行|确认执行)[。！!\s]*$/.test(message)) return confirm()
    if (pending && /^(取消|算了)[。！!\s]*$/.test(message)) {
      setPending(null); attempt.current = null; say('已取消，未执行待确认操作。'); return
    }
    lock.current = true; setBusy(true); setPending(null)
    const waitingPage = latest.current.page
    try {
      await bridge.whenReady(() => authReady.current)
      if (latest.current.page !== waitingPage) throw new Error('页面已变化，请重新发起操作。')
    } catch (error) {
      lock.current = false; setBusy(false)
      say(error instanceof Error ? error.message : '页面尚未准备好。')
      throw error
    }
    const currentContext = getContext()
    const currentFingerprint = contextFingerprint(currentContext)
    const previous = attempt.current
    const task: Attempt = previous?.message === message && previous.owner === owner() &&
      previous.fingerprint === currentFingerprint ? previous : {
        message, requestId: crypto.randomUUID(), context: currentContext,
        fingerprint: currentFingerprint, owner: owner(), confirmed: false,
      }
    attempt.current = task
    const { requestId, context, fingerprint, owner: startedOwner } = task
    setMessages(current => [...current, { role: 'user', content: message }].slice(-24))
    await bridge.dispatch({ tool: 'chat_started', arguments: { requestId, message } })
    try {
      const proposal = task.saved?.proposal ?? await apiClient.post<Proposal>('/assistant/commands/proposals', {
        request_id: requestId, message, context,
      })
      if (proposal.question) {
        attempt.current = null
        say(proposal.question)
        await bridge.dispatch({ tool: 'chat_reply', arguments: { requestId, reply: proposal.question } })
        return
      }
      const saved = { proposal, fingerprint, owner: startedOwner }
      task.saved = saved
      if (proposal.requires_confirmation && !task.confirmed) {
        setPending(saved)
        await bridge.dispatch({ tool: 'chat_reply', arguments: {
          requestId, reply: '请确认这些操作后执行，也可以回复“确认”或“取消”。' } })
        return
      }
      await perform(saved, task.confirmed)
    } catch (error) {
      // A rejected proposal has not executed. A fresh explicit retry may safely
      // obtain a new request ID; lost transport responses still reuse the old ID.
      if (error instanceof ApiError && !task.saved) attempt.current = null
      const reply = error instanceof Error ? error.message : '操作未完成。'
      say(reply)
      await bridge.dispatch({ tool: 'chat_failed', arguments: { requestId, message: reply } })
      if (error instanceof ApiError && error.status === 401) requestAccountDialog()
      throw error
    } finally {
      lock.current = false; setBusy(false)
      const next = deferred.current
      deferred.current = null
      if (next) queueMicrotask(() => { void send(next).catch(() => undefined) })
      else restoreChatFocus()
    }
  }
  const conversation = <LayerConversation label='操作助手' focusedPlace='RoamBot' busy={busy} onSend={send} status=''
    messages={messages.map((message, index) => ({ ...message, id: 'business-' + index }))}>
    {lastLink && <a className='business-result-link' href={lastLink} target='_blank' rel='noreferrer'>打开刚生成的链接</a>}
  </LayerConversation>
  return <BusinessAssistantContext.Provider value={{ bridge, send, busy, chat: conversation,
    recallSelection: (history, version) => {
      const saved = selection.current
      return saved?.owner === owner() && saved.history === history && saved.version === version ? saved.ids : []
    },
    rememberSelection: (history, version, ids) => { selection.current = { owner: owner(), history, version, ids } },
  }}>
    <Outlet />
    {location.pathname !== '/recommend' && createPortal(<div className='business-command-layer'>
      {conversation}
    </div>, document.body)}
    {pending && createPortal(<ConfirmDialog open title='确认执行这些操作？'
      message={pending.proposal.actions.map(a => labels[a.tool] ?? a.tool).join(' → ')}
      confirmLabel='确认执行' onConfirm={() => void confirm()}
      onCancel={() => { setPending(null); attempt.current = null; say('已取消，未执行待确认操作。') }}>
      <form onSubmit={event => {
        event.preventDefault()
        void send(confirmationText).then(() => setConfirmationText('')).catch(() => undefined)
      }}><label className='field'><span>也可以回复“确认”或“取消”</span>
        <input data-command-confirm aria-label='确认操作指令' maxLength={2000} value={confirmationText}
          onChange={event => setConfirmationText(event.target.value)} /></label>
      </form>
    </ConfirmDialog>, document.body)}
  </BusinessAssistantContext.Provider>
}
