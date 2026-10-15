import type { PlaceEvaluationRequest, RecommendationRequest } from '../../api/types'
import { defaultDisplayWeights, toRankingWeights, type TravelFormDraft } from '../search/formState'
import type { AssistantDraft, AssistantPatch, ConditionKey, StudioAction, StudioState } from './types'
import { emptyConversationState, readConversationState } from './assistantMemory'

export function createStudioState(draft?: TravelFormDraft): StudioState {
  return { draft: draft ?? { mode: 'recommendation', city: '', mainOrigin: '', companions: [],
    mainOriginCoordinate: null, companionOriginCoordinates: [], maxDistance: '50',
    startDate: '', endDate: '', sceneryTypes: [], matchMode: 'any', targetPlace: '', destinationRegions: [] },
    revision: 0, confirmedFields: draft?.maxDistance ? ['range'] : [], result: null, selection: [], detailId: null,
    teamPick: { active: false, batchVersion: null, candidateIds: [] },
    messages: [], conversationState: emptyConversationState(), aiStatus: '', queryStatus: '', aiRequestId: null, queryRequestId: null }
}

export function toAssistantDraft(d: TravelFormDraft): AssistantDraft {
  return { mode: d.mode, main_origin: d.mainOrigin.trim() || null,
    companion_origins: d.companions.filter(v => v.trim()), start_date: d.startDate || null,
    end_date: d.endDate || null, max_distance_km: Number(d.maxDistance) || null,
    scenery_types: d.sceneryTypes, scenery_match_mode: d.matchMode,
    scenery_query: d.sceneryQuery?.trim() || null, scenery_keywords: d.sceneryKeywords ?? [],
    destination_regions: d.destinationRegions ?? [], target_place: d.targetPlace.trim() || null,
    ...(d.weights ? { weights: toRankingWeights(d.weights, (1 + d.companions.length) as 1 | 2 | 3) } : {}) }
}

const keys: Record<keyof AssistantPatch, ConditionKey> = {
  mode: 'targetPlace', main_origin: 'mainOrigin', companion_origins: 'companions',
  start_date: 'dates', end_date: 'dates', max_distance_km: 'range', scenery_types: 'sceneryTypes',
  scenery_match_mode: 'sceneryTypes', destination_regions: 'range', target_place: 'targetPlace', weights: 'weights',
  scenery_query: 'sceneryTypes', scenery_keywords: 'sceneryTypes',
}
export function applyAssistantPatch(d: TravelFormDraft, p: AssistantPatch): TravelFormDraft {
  if (Object.keys(p).some(k => !(k in keys))) throw new Error('不支持的条件字段')
  if (('start_date' in p) !== ('end_date' in p)) throw new Error('日期需同时修改')
  const next = { ...d }
  if ('mode' in p) next.mode = p.mode ?? 'recommendation'
  if ('main_origin' in p) { next.mainOrigin = p.main_origin ?? ''; next.mainOriginCoordinate = null }
  if ('companion_origins' in p) {
    if (p.companion_origins && p.companion_origins.length > 2) throw new Error('最多两个同行出发地')
    next.companions = p.companion_origins ?? []
    next.companionOriginCoordinates = next.companions.map((name, i) => name === d.companions[i] ? d.companionOriginCoordinates[i] ?? null : null)
  }
  if ('start_date' in p) { next.startDate = p.start_date ?? ''; next.endDate = p.end_date ?? '' }
  if ('max_distance_km' in p) next.maxDistance = p.max_distance_km == null ? '' : String(p.max_distance_km)
  if ('scenery_types' in p) next.sceneryTypes = p.scenery_types ?? []
  if ('scenery_query' in p) next.sceneryQuery = p.scenery_query ?? ''
  if ('scenery_keywords' in p) next.sceneryKeywords = p.scenery_keywords ?? []
  if ('scenery_match_mode' in p) next.matchMode = p.scenery_match_mode ?? 'any'
  if ('destination_regions' in p) next.destinationRegions = p.destination_regions ?? []
  if ('target_place' in p) next.targetPlace = p.target_place ?? ''
  if ('weights' in p) {
    if (p.weights) {
      const { weather, distance, popularity } = p.weights
      const total = weather + distance + popularity
      next.weights = { weather: weather / total * 100, distance: distance / total * 100, popularity: popularity / total * 100 }
    } else next.weights = undefined
  }
  return next
}

export function studioReducer(s: StudioState, a: StudioAction): StudioState {
  switch (a.type) {
    case 'enterTeamPickMode': return { ...s, teamPick: { ...s.teamPick, active: true,
      ...(s.result?.mode === 'recommendation' ? { batchVersion: s.result.version, candidateIds: s.selection, candidateItems: s.result.items.filter(i => s.selection.includes(i.destination.provider_id)) } : {}) } }
    case 'exitTeamPickMode': return { ...s, teamPick: { active: false, batchVersion: null, candidateIds: [] } }
    case 'startNewQuery': return { ...createStudioState(), revision: s.revision + 1, teamPick: s.teamPick, newQuerySnapshot: { ...s, newQuerySnapshot: null } }
    case 'undoNewQuery': {
      if (!s.newQuerySnapshot) return s
      const snapshot = s.newQuerySnapshot
      const revision = s.revision + 1
      const result = snapshot.result && snapshot.result.submittedRevision === snapshot.revision ? { ...snapshot.result, submittedRevision: revision } : snapshot.result
      return { ...snapshot, result, revision, aiRequestId: null, queryRequestId: null, newQuerySnapshot: null }
    }
    case 'expireNewQueryUndo': return { ...s, newQuerySnapshot: null }
    case 'restartAll': return { ...createStudioState(), revision: s.revision + 1 }
    case 'removeCondition': {
      const resets: Record<ConditionKey, Partial<TravelFormDraft>> = {
        mainOrigin: { mainOrigin: '', mainOriginCoordinate: null }, dates: { startDate: '', endDate: '' },
        range: { destinationRegions: [], maxDistance: '' }, sceneryTypes: { sceneryTypes: [], sceneryQuery: '', sceneryKeywords: [] },
        companions: { companions: [], companionOriginCoordinates: [] }, weights: { weights: undefined },
        targetPlace: { targetPlace: '', mode: 'recommendation' },
      }
      return { ...s, draft: { ...s.draft, ...resets[a.key] }, revision: s.revision + 1,
        conversationState: a.key === 'dates' ? emptyConversationState() : s.conversationState,
        confirmedFields: s.confirmedFields.filter(k => k !== a.key) }
    }
    case 'restore': return a.state
    case 'edit': return { ...s, draft: a.draft, queryStatus: s.queryRequestId ? s.queryStatus : '', revision: s.revision + 1, confirmedFields: [...new Set([...s.confirmedFields, ...a.keys ?? []])],
      conversationState: a.draft.startDate !== s.draft.startDate || a.draft.endDate !== s.draft.endDate || a.keys?.includes('dates') ? emptyConversationState() : s.conversationState }
    case 'aiStarted': return { ...s, aiRequestId: a.requestId, aiStatus: '正在理解你的想法…', messages: [...s.messages, { id: a.requestId, role: 'user', content: a.message }].slice(-24) as StudioState['messages'] }
    case 'applyAssistant': {
      if (a.requestId !== s.aiRequestId) return s
      if (a.revision !== s.revision || a.response.revision !== s.revision || (a.resultVersion !== undefined && a.resultVersion !== (s.result?.version ?? null)) || (a.focusedId !== undefined && a.focusedId !== s.detailId))
        return { ...s, aiRequestId: null, aiStatus: '条件或当前地点已变化，旧回答未应用。' }
      const patch = a.response.patch ?? {}
      const edited = Object.keys(patch).length > 0
      const conversationState = a.response.conversation_state === undefined
        ? ('start_date' in patch ? emptyConversationState() : s.conversationState)
        : readConversationState(a.response.conversation_state)
      if (!conversationState) return { ...s, aiRequestId: null, aiStatus: 'AI条件未通过检查，请直接编辑。' }
      const memoryChanged = JSON.stringify(conversationState) !== JSON.stringify(s.conversationState)
      let draft = s.draft
      try { draft = applyAssistantPatch(draft, patch) } catch { return { ...s, aiRequestId: null, aiStatus: 'AI条件未通过检查，请直接编辑。' } }
      return { ...s, draft, conversationState, revision: s.revision + Number(edited || memoryChanged), aiRequestId: null, aiStatus: '',
        queryStatus: s.queryRequestId ? s.queryStatus : '',
        confirmedFields: [...new Set([...s.confirmedFields, ...Object.keys(patch).map(k => keys[k as keyof AssistantPatch])])],
        messages: [...s.messages, { id: `${a.requestId}-reply`, role: 'assistant', resultVersion: s.result?.version ?? null, content: a.response.reply + (a.response.question ? `\n${a.response.question}` : '') }].slice(-24) as StudioState['messages'] }
    }
    case 'aiFailed': return a.requestId === s.aiRequestId ? { ...s, aiRequestId: null, aiStatus: a.message } : s
    case 'queryStarted': return { ...s, queryRequestId: a.requestId, queryNoticeId: a.requestId, queryStatus: s.draft.mode === 'recommendation' ? '已开始推荐 · 正在结合天气、距离和你的偏好' : '已开始评估 · 正在结合天气和路程' }
    case 'queryFailed': return a.requestId === s.queryRequestId ? { ...s, queryRequestId: null, queryStatus: a.message } : s
    case 'querySucceeded': {
      if (a.requestId !== s.queryRequestId) return s
      if (a.revision !== s.revision) return { ...s, queryRequestId: null, queryStatus: '条件已变化，请确认后更新推荐。' }
      const unchanged = a.result.mode === 'recommendation' && s.selection.every(id => a.result.items.some(i => i.destination.provider_id === id))
      const newTeamBatch = s.teamPick.active && s.teamPick.batchVersion !== a.result.version
      const selection = unchanged ? s.selection : []
      return { ...s, result: a.result, detailId: null, selection, queryRequestId: null,
        teamPick: newTeamBatch ? { active: true, batchVersion: a.result.mode === 'recommendation' ? a.result.version : null, candidateIds: selection, candidateItems: a.result.items.filter(i => selection.includes(i.destination.provider_id)) } : s.teamPick,
        queryStatus: !a.result.items.length ? '没有找到符合条件的地点，试试调整范围。' : newTeamBatch && s.teamPick.candidateIds.length && !selection.length ? '推荐批次已变化，同行清单已清空，请重新选择。' : !unchanged ? '候选已变化，请重新选择想比较或邀请的地点。' : '' }
    }
    case 'toggleCandidate': {
      if (s.result?.mode !== 'recommendation') return s
      if (!s.result?.items.some(i => i.destination.provider_id === a.id)) return s
      const selection = s.selection.includes(a.id) ? s.selection.filter(id => id !== a.id) : s.selection.length < 3 ? [...s.selection, a.id] : s.selection
      return { ...s, selection, teamPick: s.teamPick.active ? { active: true, batchVersion: s.result.version, candidateIds: selection, candidateItems: s.result.items.filter(i => selection.includes(i.destination.provider_id)) } : s.teamPick }
    }
    case 'openDetail': return s.result?.version === a.resultVersion && s.result.items.some(i => i.destination.provider_id === a.id) ? { ...s, detailId: a.id } : s
    case 'closeDetail': return { ...s, detailId: null }
    case 'clearConversation': return { ...s, messages: [], conversationState: emptyConversationState(), aiRequestId: null, aiStatus: '' }
    case 'logout': return { ...s, result: s.result ? { ...s.result, historyOwner: null, assistantContext: undefined } : null, aiRequestId: null, newQuerySnapshot: null }
  }
}

function validDate(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value
}
export function buildStudioRequest(s: StudioState, today: string): RecommendationRequest | PlaceEvaluationRequest {
  const d = s.draft
  if (!d.mainOrigin.trim()) throw new Error('请补充主出发地。')
  const last = new Date(`${today}T00:00:00Z`); last.setUTCDate(last.getUTCDate() + 6)
  if (!validDate(d.startDate) || !validDate(d.endDate) || d.startDate < today || d.endDate < d.startDate || d.endDate > last.toISOString().slice(0, 10)) throw new Error('请选择未来7天内的有效日期。')
  if (d.companions.length > 2 || d.companions.some(v => !v.trim())) throw new Error('请填写同行出发地，最多两个。')
  const regions = d.destinationRegions ?? []
  const distance = Number(d.maxDistance)
  if (!regions.length && (!(distance > 0) || distance > 500)) throw new Error('距离需为大于0、不超过500km。')
  const weights = toRankingWeights(d.weights ?? defaultDisplayWeights, (1 + d.companions.length) as 1 | 2 | 3)
  if (Object.values(weights).some(v => !Number.isFinite(v) || v < 0) || Math.abs(Object.values(weights).reduce((a,b) => a+b,0) - 100) > 1e-6) throw new Error('偏好权重合计需为100。')
  const base = { city: '', main_origin: d.mainOrigin.trim(), companion_origins: d.companions.map(v => v.trim()),
    main_origin_coordinate: d.mainOriginCoordinate, companion_origin_coordinates: d.companions.map((_, i) => d.companionOriginCoordinates[i] ?? null),
    max_distance_km: regions.length ? 500 : distance, start_date: d.startDate, end_date: d.endDate, weights }
  if (d.mode === 'place_evaluation') {
    if (!d.targetPlace.trim()) throw new Error('请补充目标地点。')
    return { ...base, target_place: d.targetPlace.trim() }
  }
  if (!d.sceneryTypes.length && !regions.length && !d.sceneryQuery?.trim() && !d.sceneryKeywords?.length) throw new Error('请说说想找什么地方。')
  return { ...base, scenery_types: d.sceneryTypes.length ? d.sceneryTypes : ['lake','sea','old_town','museum','park','mountain'], scenery_match_mode: d.matchMode, destination_regions: regions,
    ...(d.sceneryQuery ? { scenery_query: d.sceneryQuery } : {}), ...(d.sceneryKeywords?.length ? { scenery_keywords: d.sceneryKeywords } : {}) }
}
