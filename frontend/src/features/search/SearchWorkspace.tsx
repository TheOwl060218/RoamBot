import type { PlaceEvaluationRequest, PlaceEvaluationResponse, RecommendationRequest, RecommendationResponse } from '../../api/types'
import type { RestoredHistorySearch } from '../history/restoreHistorySearch'
import { StudioWorkspace } from '../studio/StudioWorkspace'
export type SearchResult = (RecommendationResponse | PlaceEvaluationResponse) & {
  query_request?: RecommendationRequest | PlaceEvaluationRequest
  history_owner?: string | null
}
export type SearchWorkspaceProps = {
  initialMode?: 'recommendation' | 'place_evaluation'
  initialTarget?: string
  restoredSearch?: RestoredHistorySearch
  startTeamPick?: boolean
}
export function SearchWorkspace(props: SearchWorkspaceProps) { return <StudioWorkspace {...props} /> }
