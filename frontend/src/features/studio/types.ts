import type { PlaceEvaluationRequest, RankingWeights, RecommendationItem, RecommendationRequest, SceneryType, SearchMode, SourceState } from '../../api/types'
import type { TravelFormDraft } from '../search/formState'

export type ConditionKey = 'mainOrigin' | 'companions' | 'dates' | 'sceneryTypes' | 'range' | 'targetPlace' | 'weights'
export type AssistantDraft = {
  mode?: SearchMode | null; main_origin?: string | null; companion_origins?: string[] | null
  start_date?: string | null; end_date?: string | null; max_distance_km?: number | null
  scenery_types?: SceneryType[] | null; scenery_match_mode?: 'any' | 'cover_all' | null
  scenery_query?: string | null; scenery_keywords?: string[] | null
  destination_regions?: string[] | null; target_place?: string | null; weights?: RankingWeights | null
}
export type AssistantPatch = AssistantDraft
export type AssistantConversationState = {
  pending_date_request: { start_date?: string | null; end_date?: string | null; offset_days?: number | null; duration_days?: number | null } | null
}
export type ChatMessage = { id: string; role: 'user' | 'assistant'; content: string; resultVersion?: number | null }
export type AssistantTurnRequest = {
  message: string; revision: number; draft: AssistantDraft
  history: { role: 'user' | 'assistant'; content: string }[]
  conversation_state?: AssistantConversationState
  assistant_context?: string; focused_destination_id?: string
}
export type AssistantTurnResponse = {
  revision: number; reply: string; patch?: AssistantPatch; confirmed_fields?: string[]
  question?: string | null; quick_replies?: string[]; unsupported_preferences?: string[]
  source: 'live' | 'demo' | 'degraded'
  conversation_state?: AssistantConversationState
}
export type StudioResult = {
  version: number; mode: SearchMode; items: RecommendationItem[]; source_state: SourceState
  generated_at: string; queryRequest: RecommendationRequest | PlaceEvaluationRequest | null
  submittedRevision: number; historyId: string | null; historyOwner: string | null
  assistantContext?: string
}
export type StudioState = {
  teamPick: { active: boolean; batchVersion: number | null; candidateIds: string[]; candidateItems?: RecommendationItem[] }
  newQuerySnapshot?: StudioState | null
  draft: TravelFormDraft; revision: number; confirmedFields: ConditionKey[]
  result: StudioResult | null; selection: string[]; detailId: string | null
  messages: ChatMessage[]; aiStatus: string; queryStatus: string; queryNoticeId?: string
  conversationState: AssistantConversationState
  aiRequestId: string | null; queryRequestId: string | null
}
export type StudioAction =
  | { type: 'edit'; draft: TravelFormDraft; keys?: ConditionKey[] }
  | { type: 'aiStarted'; requestId: string; message: string }
  | { type: 'applyAssistant'; requestId: string; revision: number; response: AssistantTurnResponse; resultVersion?: number | null; focusedId?: string | null }
  | { type: 'aiFailed'; requestId: string; message: string }
  | { type: 'queryStarted'; requestId: string }
  | { type: 'querySucceeded'; requestId: string; revision: number; result: StudioResult }
  | { type: 'queryFailed'; requestId: string; message: string }
  | { type: 'toggleCandidate'; id: string }
  | { type: 'openDetail'; id: string; resultVersion: number }
  | { type: 'closeDetail' } | { type: 'clearConversation' } | { type: 'logout' }
  | { type: 'restore'; state: StudioState }
  | { type: 'removeCondition'; key: ConditionKey }
  | { type: 'startNewQuery' } | { type: 'undoNewQuery' } | { type: 'expireNewQueryUndo' } | { type: 'restartAll' }
  | { type: 'enterTeamPickMode' } | { type: 'exitTeamPickMode' }

export type StudioPhase = 'query.idle' | 'query.parsing' | 'query.ready' | 'query.searching' | 'transition.toResults' | 'results.ready' | 'transition.toQuery'
export type ConditionCard = { id: string; key: ConditionKey; label: string; value: string; supplemental: boolean }
export type ResultRailCard = ConditionCard
