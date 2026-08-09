import { useLocation } from 'react-router-dom'

import { SearchWorkspace } from '../features/search/SearchWorkspace'

export function SearchPage() {
  const location = useLocation()
  const target = (location.state as { evaluationTarget?: string } | null)?.evaluationTarget
  return (
    <SearchWorkspace
      initialMode={target ? 'place_evaluation' : 'recommendation'}
      initialTarget={target}
    />
  )
}
