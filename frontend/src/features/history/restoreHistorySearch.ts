import type { HistoryDetail } from '../../api/types'
import type { SearchResult } from '../search/SearchWorkspace'
import {
  draftFromRequest, saveSearchResult, saveSelectedPlaceId, saveTravelDraft,
  type TravelFormDraft,
} from '../search/formState'

export type RestoredHistorySearch = { result: SearchResult; draft: TravelFormDraft }

export function restoreHistorySearch(history: HistoryDetail, username: string | null): RestoredHistorySearch {
  const request = history.request
  const draft = draftFromRequest(request)
  const result: SearchResult = { ...history.result, query_request: request,
    history_id: history.id, history_owner: username }
  saveTravelDraft(draft)
  saveSearchResult(result)
  const items = 'items' in result ? result.items : [result.item]
  saveSelectedPlaceId(items[0]?.destination.provider_id ?? '')
  return { result, draft }
}
