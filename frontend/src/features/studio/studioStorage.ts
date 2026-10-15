import { loadTravelDraft, saveTravelDraft, loadSearchResult } from '../search/formState'
import type { SearchResult } from '../search/SearchWorkspace'
import { createStudioState } from './studioState'
import { readConversationState } from './assistantMemory'
import type { StudioState } from './types'
import { isStoredDraft, isStoredItem, isStoredSource, isStoredRequest } from './storedValidation'

const KEY = 'roambot.studio.session.v1'
export function loadStudioState(): StudioState {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (raw) {
      const saved = JSON.parse(raw)
      if ([1, 2].includes(saved.version) && isStoredDraft(saved.draft)) {
        const s = createStudioState(saved.draft)
        s.conversationState = readConversationState(saved.conversationState) ?? s.conversationState
        s.confirmedFields = ['mainOrigin','dates','range','sceneryTypes','companions','weights','targetPlace'].filter(k => Array.isArray(saved.confirmedFields) && saved.confirmedFields.includes(k)) as StudioState['confirmedFields']
        if (saved.result && Array.isArray(saved.result.items) && saved.result.items.length <= 7 && saved.result.items.every(isStoredItem) && isStoredSource(saved.result.source_state)
          && ['recommendation','place_evaluation'].includes(saved.result.mode) && Number.isInteger(saved.result.version) && Number.isInteger(saved.result.submittedRevision) && typeof saved.result.generated_at === 'string') {
          s.result = { ...saved.result, assistantContext: undefined, historyOwner: null,
            queryRequest: isStoredRequest(saved.result.queryRequest) ? saved.result.queryRequest : null }
          s.revision = Number.isInteger(saved.revision) && saved.revision >= 0 ? saved.revision : saved.result.submittedRevision
        }
        return s
      }
    }
  } catch { /* Corrupt storage does not block an in-memory session. */ }
  const draft = loadTravelDraft()
  const s = createStudioState(isStoredDraft(draft) ? draft : undefined)
  const legacy = loadSearchResult<SearchResult>()
  if (legacy && ('items' in legacy || 'item' in legacy) && isStoredSource(legacy.source_state) && ('items' in legacy ? Array.isArray(legacy.items) && legacy.items.length <= 7 && legacy.items.every(isStoredItem) : isStoredItem(legacy.item))) {
    s.result = { version: 0, mode: 'items' in legacy ? 'recommendation' : 'place_evaluation', items: 'items' in legacy ? legacy.items : [legacy.item], source_state: legacy.source_state, generated_at: legacy.generated_at, submittedRevision: 0, historyId: 'history_id' in legacy ? legacy.history_id ?? null : null, historyOwner: null, queryRequest: isStoredRequest(legacy.query_request) ? legacy.query_request : null }
  }
  return s
}
export function saveStudioState(s: StudioState) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ version: 2, revision: s.revision, draft: s.draft, confirmedFields: s.confirmedFields, conversationState: s.conversationState,
      result: s.result ? Object.fromEntries(Object.entries(s.result).filter(([key]) => key !== 'assistantContext' && key !== 'historyOwner')) : null },
      (key, value) => key === 'assistant_context' || key === 'assistantContext' ? undefined : value))
    saveTravelDraft(s.draft)
  } catch { /* Optional continuity only. */ }
}
