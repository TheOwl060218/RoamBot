import type { ReactNode } from 'react'

import type { StudioState } from './types'

export function StudioStage({ state, children }: { state: StudioState; children: ReactNode }) {
  const phase = state.messages.length ? 'conversation' : 'intro'
  return <section className={`studio-stage studio-stage-${phase}`} data-stage={phase}>{children}</section>
}
