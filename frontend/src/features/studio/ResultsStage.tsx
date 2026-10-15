import type { ReactNode } from 'react'
import type { WorkspacePhase } from './useStudioStage'
export function ResultsStage({ phase, children, onReturn, onNew }: {
  phase: WorkspacePhase; children: ReactNode; onReturn: () => void; onNew: () => void
}) {
  const active = phase === 'results'
  return <div className='studio-results-page' aria-hidden={!active} inert={!active}>
    <nav className='studio-result-navigation' aria-label='查询操作'>
      <button type='button' onClick={onReturn}>← 返回修改</button>
      <button type='button' onClick={onNew}>↻ 新查询</button>
    </nav>
    {children}
  </div>
}
