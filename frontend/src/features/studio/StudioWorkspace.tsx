import { useEffect, useLayoutEffect, useReducer, useRef, useState } from 'react'
import { useInRouterContext } from 'react-router-dom'
import { CreatePlanControl } from '../plans/CreatePlanControl'
import { createStudioState, studioReducer, toAssistantDraft } from './studioState'
import { loadStudioState, saveStudioState } from './studioStorage'
import { ConditionPuzzle } from './ConditionPuzzle'
import { ConditionEditor } from './ConditionEditor'
import { StudioMenu } from './StudioMenu'
import { Composer } from './Composer'
import { useAssistant } from './useAssistant'
import { useStudioSearch } from './useStudioSearch'
import { useAuth } from '../auth/authContext'
import { SourceNotice } from '../search/SourceNotice'
import { DestinationCard } from './DestinationCard'
import { DestinationDetail } from './DestinationDetail'
import { CandidateDock } from './CandidateDock'
import { ComparisonCards } from './ComparisonCards'
import { useDetailTransition } from './useDetailTransition'
import { useStudioFavorites } from './useStudioFavorites'
import { LocationMapDialog } from '../search/LocationMapDialog'
import type { ConditionKey, StudioState } from './types'
import type { SearchWorkspaceProps } from '../search/SearchWorkspace'
import { StudioStage } from './StudioStage'
import { useCoastalMotion } from './useCoastalMotion'
import { ConditionPocket } from './ConditionPocket'
import { useStudioStage } from './useStudioStage'
import { ResultsStage } from './ResultsStage'
import { OverlayHost } from './OverlayHost'
import { requestAccountDialog } from '../../app/accountDialog'
import { usePuzzleMotion } from './usePuzzleMotion'
import { projectConditionCards } from './conditionProjection'
import { QueryNotice } from './QueryNotice'
import { afterLayerExits } from './layerMotion'
import { LayerConversation } from './LayerConversation'
import { useBusinessAssistant, useCommandTarget } from '../commands/commandContext'
import type { RecommendationResponse, PlaceEvaluationResponse, RecommendationRequest, PlaceEvaluationRequest } from '../../api/types'
import type { AssistantTurnResponse } from './types'

function candidateElement(id: string) { return [...document.querySelectorAll<HTMLElement>('[data-candidate-id]')].find(node => node.dataset.candidateId === id) ?? null }
function detailElement(id: string) { return [...document.querySelectorAll<HTMLElement>('[data-detail-id]')].find(node => node.dataset.detailId === id) ?? null }

function initialState({ initialMode, initialTarget, restoredSearch, startTeamPick }: SearchWorkspaceProps): StudioState {
  const s = restoredSearch ? createStudioState(restoredSearch.draft) : loadStudioState()
  if (restoredSearch) {
    const r = restoredSearch.result
    s.result = { version: 1, mode: 'items' in r ? 'recommendation' : 'place_evaluation', items: 'items' in r ? r.items : [r.item],
      source_state: r.source_state, generated_at: r.generated_at, queryRequest: r.query_request ?? null,
      submittedRevision: 0, historyId: 'history_id' in r ? r.history_id ?? null : null, historyOwner: r.history_owner ?? null }
  }
  if (initialTarget) { s.draft = { ...s.draft, mode: initialMode ?? 'place_evaluation', targetPlace: initialTarget }; s.result = null }
  if (startTeamPick) {
    s.draft = { ...s.draft, mode: 'recommendation' }
    if (s.result?.mode === 'place_evaluation') s.result = null
    return studioReducer(s, { type: 'enterTeamPickMode' })
  }
  return s
}
export function StudioWorkspace(props: SearchWorkspaceProps) {
  const workspace = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const header = document.querySelector<HTMLElement>('.shell-header')
    const measure = () => workspace.current?.style.setProperty('--studio-header-height', `${header?.offsetHeight ?? 0}px`)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    if (header) observer?.observe(header)
    window.addEventListener('resize', measure)
    measure()
    return () => { observer?.disconnect(); window.removeEventListener('resize', measure) }
  }, [])
  const business = useBusinessAssistant()
  const [state, dispatch] = useReducer(studioReducer, props, args => {
    const restored = initialState(args)
    if (restored.result) restored.selection = business?.recallSelection?.(
      restored.result.historyId, restored.result.version)?.filter(id =>
      restored.result?.items.some(item => item.destination.provider_id === id)) ?? []
    return restored
  })
  const [editor, setEditor] = useState<ConditionKey | null>(null)
  const deferredEditor = useRef<(() => void) | null>(null)
  const [comparing, setComparing] = useState(false)
  const [favoritesOpen, setFavoritesOpen] = useState(false)
  const [otherOpen, setOtherOpen] = useState(false)
  const [pendingScenery, setPendingScenery] = useState('')
  const { user } = useAuth()
  const inRouter = useInRouterContext()
  const previousUser = useRef(user?.username ?? null)
  const incoming = useRef(props.restoredSearch ?? props.initialTarget)
  const legacyAi = useAssistant(state, dispatch)
  useEffect(() => {
    if (state.result) business?.rememberSelection?.(state.result.historyId, state.result.version, state.selection)
  }, [state.result, state.selection, business])
  const sendAssistant = business?.send ?? legacyAi.send
  const search = useStudioSearch(state, dispatch, user?.username ?? null)
  const stage = useStudioStage(state, dispatch)
  useEffect(() => () => deferredEditor.current?.(), [])
  usePuzzleMotion(state, stage.phase)
  const favorite = useStudioFavorites(user?.username ?? null, state.result?.source_state)
  const { run: runMotion } = useCoastalMotion()
  const layers = useDetailTransition(state.detailId, state.result?.version, id => dispatch(id ? { type: 'openDetail', id, resultVersion: state.result?.version ?? 0 } : { type: 'closeDetail' }))
  const detail = state.result?.items.find(i => i.destination.provider_id === state.detailId)
  const chosen = state.result?.items.filter(i => state.selection.includes(i.destination.provider_id)) ?? []
  useEffect(() => { saveStudioState(state) }, [state])
  useEffect(() => {
    if (!pendingScenery) return
    const timer = setTimeout(() => { setPendingScenery(''); void sendAssistant(`想找的地方：${pendingScenery}`).catch(() => undefined) }, 0)
    return () => clearTimeout(timer)
  }, [pendingScenery, sendAssistant])
  useEffect(() => {
    const next = props.restoredSearch ?? props.initialTarget
    if (next !== incoming.current && next) { incoming.current = next; dispatch({ type: 'restore', state: initialState(props) }) }
  }, [props])
  useEffect(() => {
    if (previousUser.current !== (user?.username ?? null)) dispatch({ type: 'logout' })
    previousUser.current = user?.username ?? null
  }, [user?.username])
  const dirty = !!state.result && state.revision !== state.result.submittedRevision
  const detailId = detail?.destination.provider_id
  useEffect(() => {
    if (!detailId) return
    const frame = requestAnimationFrame(() => runMotion(
      candidateElement(detailId),
      detailElement(detailId),
      detailId,
    ))
    return () => cancelAnimationFrame(frame)
  }, [detailId, runMotion])
  function closeDetail() {
    if (!detail) return
    layers.close()
  }
  function openResultEditor(key: ConditionKey) {
    deferredEditor.current?.(); deferredEditor.current = null
    setEditor(key)
  }
  function editOtherPreference(key: ConditionKey) {
    setOtherOpen(false)
    deferredEditor.current?.()
    deferredEditor.current = afterLayerExits(() => { deferredEditor.current = null; setEditor(key) })
  }
  useCommandTarget('studio', () => ({
    history_id: state.result?.historyId ?? null,
    selected_ids: state.selection, focused_id: state.detailId,
    visible_places: state.result?.items.map(item => ({ id: item.destination.provider_id, name: item.destination.name })) ?? [],
    result_version: state.result?.version ?? null, dirty,
    layer: layers.mapOpen ? 'map' : comparing ? 'comparison' : editor ? 'editor' : detail ? 'detail' : stage.phase,
    assistant_turn: { message: '当前条件', revision: state.revision, draft: toAssistantDraft(state.draft),
      conversation_state: state.conversationState,
      history: state.messages.slice(-6).map(({ role, content }) => ({ role, content: content.slice(0, 1000) })),
      ...(state.result?.assistantContext ? { assistant_context: state.result.assistantContext } : {}),
      ...(state.detailId ? { focused_destination_id: state.detailId } : {}) },
  }), async effect => {
    const args = effect.arguments
    const requestId = String(args.requestId ?? '')
    if (effect.tool === 'chat_started') {
      dispatch({ type: 'aiStarted', requestId, message: String(args.message) })
    } else if (effect.tool === 'assistant_result') {
      if (Object.keys((args.response as AssistantTurnResponse).patch ?? {}).length) setEditor(null)
      dispatch({ type: 'applyAssistant', requestId, revision: state.revision,
        resultVersion: state.result?.version ?? null, focusedId: state.detailId,
        response: args.response as AssistantTurnResponse })
    } else if (effect.tool === 'chat_reply') {
      dispatch({ type: 'applyAssistant', requestId, revision: state.revision,
        response: { revision: state.revision, reply: String(args.reply), source: 'live' } })
    } else if (effect.tool === 'chat_failed') {
      dispatch({ type: 'aiFailed', requestId, message: String(args.message) })
    } else if (effect.tool === 'query_result') {
      const response = args.query as RecommendationResponse | PlaceEvaluationResponse
      const queryId = crypto.randomUUID()
      dispatch({ type: 'queryStarted', requestId: queryId })
      dispatch({ type: 'querySucceeded', requestId: queryId, revision: state.revision, result: {
        version: (state.result?.version ?? 0) + 1, mode: 'items' in response ? 'recommendation' : 'place_evaluation',
        items: 'items' in response ? response.items : [response.item],
        source_state: response.source_state, generated_at: response.generated_at,
        queryRequest: args.query_request as RecommendationRequest | PlaceEvaluationRequest,
        submittedRevision: state.revision, historyId: 'history_id' in response ? response.history_id ?? null : null,
        historyOwner: user?.username ?? null, assistantContext: response.assistant_context ?? undefined,
      } })
    } else if (effect.tool === 'select_candidates') {
      const ids = args.ids as string[]
      if (!ids.every(id => state.result?.items.some(i => i.destination.provider_id === id)))
        throw new Error('候选已变化，请重新选择。')
      for (const id of new Set([...state.selection, ...ids])) {
        if (state.selection.includes(id) !== ids.includes(id)) dispatch({ type: 'toggleCandidate', id })
      }
    } else if (effect.tool === 'open_detail' || effect.tool === 'open_map') {
      const id = String(args.id)
      if (!state.result?.items.some(i => i.destination.provider_id === id))
        throw new Error('地点不在当前结果中。')
      if (state.detailId !== id) {
        if (layers.mapOpen) throw new Error('请先关闭当前地图再切换地点。')
        layers.open(id)
        if (effect.tool === 'open_map') {
          await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
          await business?.bridge.perform(effect)
        }
      } else if (effect.tool === 'open_map') layers.openMap()
    } else if (effect.tool === 'close_layer') {
      if (layers.mapOpen) layers.closeMap()
      else if (comparing) setComparing(false)
      else if (editor) setEditor(null)
      else if (otherOpen) setOtherOpen(false)
      else if (favoritesOpen) setFavoritesOpen(false)
      else if (detail) closeDetail()
      else return false
    } else if (effect.tool === 'show_comparison') {
      const ids = args.ids as string[] | undefined
      if (ids) {
        if (ids.length < 2 || ids.length > 3 || new Set(ids).size !== ids.length ||
          !ids.every(id => state.result?.items.some(i => i.destination.provider_id === id)))
          throw new Error('比较候选已变化，请重新选择。')
        for (const id of new Set([...state.selection, ...ids])) {
          if (state.selection.includes(id) !== ids.includes(id)) dispatch({ type: 'toggleCandidate', id })
        }
      } else if (chosen.length < 2) throw new Error('请至少选择两个地点。')
      setComparing(true)
    } else if (effect.tool === 'show_candidates') {
      workspace.current?.querySelector('.destination-grid')?.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
        block: 'center' })
    } else if (effect.tool === 'edit_condition') setEditor(args.field as ConditionKey)
    else if (effect.tool === 'show_preferences') setOtherOpen(true)
    else if (effect.tool === 'choose_favorite') {
      if (!user) requestAccountDialog()
      else setFavoritesOpen(true)
    } else if (effect.tool === 'start_team_pick') dispatch({ type: 'enterTeamPickMode' })
    else if (effect.tool === 'end_team_pick') dispatch({ type: 'exitTeamPickMode' })
    else if (effect.tool === 'start_new_query') stage.startNewQuery()
    else if (effect.tool === 'undo_new_query') stage.undoNewQuery()
    else if (effect.tool === 'clear_conversation') dispatch({ type: 'clearConversation' })
    else if (effect.tool === 'open_external_map') {
      const item = state.result?.items.find(i => i.destination.provider_id === args.id)
      if (!item) throw new Error('地点已变化。')
      const c = item.destination.coordinate
      const url = 'https://uri.amap.com/marker?position=' + c.longitude + ',' + c.latitude +
        '&name=' + encodeURIComponent(item.destination.name) + '&coordinate=gaode&callnative=0'
      const opened = window.open(url, '_blank')
      if (opened) opened.opener = null
      else throw new Error('浏览器拦截了新窗口，请使用详情中的高德入口。')
    } else return false
    return true
  })
  const featureMenu = <StudioMenu onEdit={setEditor} onNew={stage.restartAll} onClear={() => undefined} onFavorites={() => user ? setFavoritesOpen(true) : requestAccountDialog()}
    onTeam={() => dispatch({ type: 'enterTeamPickMode' })} />
  const composer = <Composer busy={!!state.aiRequestId} onSend={sendAssistant} focusedPlace={detail?.destination.name}>{featureMenu}</Composer>
  const recentMessages = state.messages.slice(-2)
  const latestAssistant = [...state.messages].reverse().find(message => message.role === 'assistant' && message.resultVersion === state.result?.version)
  return <div ref={workspace} className={`studio-workspace spatial-workspace phase-${stage.phase}`} data-workspace-phase={stage.phase}>
    <div className='studio-query-page' aria-hidden={stage.phase !== 'query'} inert={stage.phase !== 'query'}>
    <StudioStage state={state}>
      <div className='studio-stage-copy'>
        <header className='studio-intro'><h1>想去哪儿？</h1></header>
        {recentMessages.length > 0 && <section className='studio-conversation studio-conversation-current' aria-label='最近对话'>{recentMessages.map(m => <p key={m.id} className={m.role}>{m.content}</p>)}</section>}
      </div>
        {state.queryStatus && !state.queryRequestId && <p className='studio-query-feedback'>{state.queryStatus}</p>}
      <div className='studio-stage-controls'>
        <ConditionPocket><ConditionPuzzle state={state} onEdit={setEditor} onRemove={key => dispatch({ type: 'removeCondition', key })} /></ConditionPocket>
        <div className='studio-actions'>
        <button type='button' className='primary-button studio-search' disabled={!!state.queryRequestId || !!state.aiRequestId} onClick={() => void search.submit().catch(() => undefined)}>{state.queryRequestId ? '正在查询…' : state.draft.mode === 'place_evaluation' ? '评估这个地点' : '开始推荐'}<span aria-hidden='true'>↗</span></button></div>
      </div>
    </StudioStage>
    </div>
    {state.queryStatus && <QueryNotice key={`${state.queryNoticeId}:${state.queryStatus}`} message={state.queryStatus} busy={!!state.queryRequestId} />}
    {state.result && <ResultsStage phase={stage.phase} onReturn={stage.returnToQuery} onNew={stage.startNewQuery}>
    <ConditionPuzzle state={state} onEdit={openResultEditor} onOther={() => { deferredEditor.current?.(); deferredEditor.current = null; setOtherOpen(true) }} layout='compact' />
    {latestAssistant && <p className='studio-ai-note'>{latestAssistant.content}</p>}
    {dirty && <p className='studio-dirty'>条件已修改 · <button type='button' className='text-button' disabled={!!state.queryRequestId || !!state.aiRequestId}
      onClick={() => void search.submit().catch(() => undefined)}>{state.queryRequestId ? '正在更新…' : state.draft.mode === 'place_evaluation' ? '更新评估' : '更新推荐'}</button></p>}
    <section className='studio-results' aria-label='推荐地点'>
      <SourceNotice source={state.result.source_state} />
      {detail && <OverlayHost label={`${detail.destination.name}详情`} onClose={closeDetail} className='destination-detail-layer' panelClassName='studio-detail-host'
        accessory={<LayerConversation label='详情对话' focusedPlace={detail.destination.name} messages={state.messages} status={state.aiStatus} busy={!!state.aiRequestId} onSend={sendAssistant} />}>
        <DestinationDetail key={detail.destination.provider_id} item={detail} selected={state.selection.includes(detail.destination.provider_id)} full={state.selection.length >= 3}
          onClose={closeDetail} onMap={layers.openMap} onSelect={() => dispatch({ type: 'toggleCandidate', id: detail.destination.provider_id })}
          onFavorite={() => void favorite.toggle(detail)} isFavorite={!!favorite.favorites[detail.destination.provider_id]} favoritePending={favorite.pending.includes(detail.destination.provider_id)} allowCandidate={state.result.mode === 'recommendation'} teamMode={state.teamPick.active} />
      </OverlayHost>}
      <div className='destination-grid' aria-hidden={!!detail} inert={!!detail}>{state.result.items.map(item => <DestinationCard key={item.destination.provider_id} item={item} all={state.result!.items} selected={state.selection.includes(item.destination.provider_id)} full={state.selection.length >= 3}
          onOpen={() => layers.open(item.destination.provider_id)} onToggle={() => dispatch({ type: 'toggleCandidate', id: item.destination.provider_id })} allowCandidate={state.result!.mode === 'recommendation'} teamMode={state.teamPick.active} />)}</div>
      {state.result.mode === 'recommendation' && !detail && <CandidateDock items={chosen} onRemove={id => dispatch({ type: 'toggleCandidate', id })} onCompare={() => setComparing(true)}
        hint={inRouter ? dirty ? '条件已修改，请先更新推荐再邀请同行。' : chosen.length < 2 ? `再选 ${2 - chosen.length} 个地点即可发起` : undefined : undefined}>
        {inRouter && <CreatePlanControl compact historyId={state.result.historyId} trusted={!!user && state.result.historyOwner === user.username}
          dirty={dirty} selectedIds={state.selection} city={chosen[0]?.destination.city ?? ''} startDate={state.result.queryRequest?.start_date ?? state.draft.startDate} endDate={state.result.queryRequest?.end_date ?? state.draft.endDate}
          originCount={state.result.queryRequest ? 1 + state.result.queryRequest.companion_origins.length : 1} onRerun={search.submit} />}
      </CandidateDock>}
      {comparing && chosen.length >= 2 && <OverlayHost label='候选对比' onClose={() => setComparing(false)} className='studio-comparison-layer' panelClassName='studio-detail-host'
        accessory={<LayerConversation label='比较对话' focusedPlace='候选比较' messages={state.messages} status={state.aiStatus} busy={!!state.aiRequestId} onSend={sendAssistant} />}>
        <ComparisonCards items={chosen} onClose={() => setComparing(false)} /></OverlayHost>}
    </section></ResultsStage>}
    {state.teamPick.active && <div className='studio-team-mode' role='status'>同行挑选中<button type='button' onClick={() => dispatch({ type: 'exitTeamPickMode' })}>结束挑选</button></div>}
    {state.newQuerySnapshot && stage.phase === 'query' && <div className='studio-undo-query' role='status'>已开始新查询 <button type='button' onClick={stage.undoNewQuery}>撤销</button></div>}
    {state.aiStatus && <div className='studio-assistant-recovery' data-busy={state.aiRequestId ? 'true' : undefined}><p role='status'>{state.aiStatus}</p>{!state.aiRequestId && <div>
      {!state.draft.mainOrigin && <button type='button' onClick={() => setEditor('mainOrigin')}>补充出发地</button>}
      {!state.draft.startDate && <button type='button' onClick={() => setEditor('dates')}>选择日期</button>}
      {!state.draft.sceneryTypes.length && !state.draft.destinationRegions?.length && <button type='button' onClick={() => setEditor('sceneryTypes')}>描述想找的地方</button>}
    </div>}</div>}
    {favorite.notice && <p role='status'>{favorite.notice}</p>}
    {editor && <ConditionEditor key={editor} conditionKey={editor} draft={state.draft} onSave={draft => { dispatch({ type: 'edit', draft, keys: [editor] }); setEditor(null); if (editor === 'sceneryTypes' && draft.sceneryQuery?.trim()) setPendingScenery(draft.sceneryQuery) }} onClose={() => setEditor(null)}
      accessory={<LayerConversation label='条件对话' focusedPlace='编辑条件' messages={state.messages} status={state.aiStatus} busy={!!state.aiRequestId} onSend={sendAssistant} />} />}
    {otherOpen && <OverlayHost label='其他偏好' onClose={() => setOtherOpen(false)} panelClassName='studio-feature-library glass-panel'
      accessory={<LayerConversation label='偏好对话' focusedPlace='其他偏好' messages={state.messages} status={state.aiStatus} busy={!!state.aiRequestId} onSend={sendAssistant} />}>
      <h2>其他偏好</h2>
      {projectConditionCards(state).filter(card => card.supplemental).map(card => <button type='button' key={card.id} onClick={() => editOtherPreference(card.key)}>{card.label}<small>{card.value}</small></button>)}
    </OverlayHost>}
    {favoritesOpen && <OverlayHost label='从收藏中选择' onClose={() => setFavoritesOpen(false)} panelClassName='studio-feature-library glass-panel'
      accessory={<LayerConversation label='收藏选择对话' focusedPlace='选择收藏' messages={state.messages} status={state.aiStatus} busy={!!state.aiRequestId} onSend={sendAssistant} />}>
      <h2>从收藏中选择</h2>
      {Object.values(favorite.favorites).map(item => <button type='button' key={item.id} onClick={() => {
        dispatch({ type: 'edit', draft: { ...state.draft, mode: 'place_evaluation', targetPlace: item.place.name }, keys: ['targetPlace'] })
        setFavoritesOpen(false); stage.returnToQuery()
      }}>{item.place.name}<small>{item.place.city}</small></button>)}
      {!Object.keys(favorite.favorites).length && <p>还没有收藏的地点。</p>}
    </OverlayHost>}
    <div hidden={layers.mapOpen || !!detail} inert={layers.mapOpen || !!detail}>{composer}</div>
    {layers.mapOpen && detail && state.result && <LocationMapDialog items={state.result.items} selectedId={detail.destination.provider_id}
      onSelect={item => dispatch({ type: 'openDetail', id: item.destination.provider_id, resultVersion: state.result!.version })} onClose={layers.closeMap}>
      <LayerConversation label='地图对话' focusedPlace={detail.destination.name} messages={state.messages} status={state.aiStatus} busy={!!state.aiRequestId} onSend={sendAssistant} />
    </LocationMapDialog>}
  </div>
}
