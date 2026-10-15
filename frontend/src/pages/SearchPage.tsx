import { useLocation } from 'react-router-dom'

import { SearchWorkspace } from '../features/search/SearchWorkspace'
import type { RestoredHistorySearch } from '../features/history/restoreHistorySearch'

export function SearchPage() {
  const location = useLocation()
  const state = location.state as { evaluationTarget?: string; restoredSearch?: RestoredHistorySearch; startTeamPick?: boolean } | null
  const target = state?.evaluationTarget
  return (
    <SearchWorkspace
      restoredSearch={state?.restoredSearch}
      initialMode={target ? 'place_evaluation' : 'recommendation'}
      initialTarget={target}
      startTeamPick={state?.startTeamPick}
    />
  )
}
