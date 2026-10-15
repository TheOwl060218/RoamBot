import { useCallback, useEffect, useLayoutEffect, useRef, useState, type Dispatch } from 'react'
import type { StudioAction, StudioState } from './types'
import { afterLayerExits } from './layerMotion'

export type WorkspacePhase = 'query' | 'toResults' | 'results' | 'toQuery'
const HISTORY_KEY = 'roambotStudioStage'
const HISTORY_SLOT = 'roambotStudioStageSlot'
const RESULT_SLOT = 'roambotStudioResultSlot'
export function useStudioStage(state: StudioState, dispatch: Dispatch<StudioAction>) {
  const [phase, setPhase] = useState<WorkspacePhase>(
    state.result?.items.length && window.history.state?.[HISTORY_SLOT] && window.history.state?.[HISTORY_KEY] === window.history.state?.[HISTORY_SLOT] ? 'results'
      : window.history.state?.[HISTORY_SLOT] && !window.history.state?.[HISTORY_KEY] ? 'query'
      : state.result && state.result.submittedRevision === state.revision ? 'results' : 'query')
  const seen = useRef(state.result?.version ?? null)
  const owner = useRef(window.history.state?.[HISTORY_SLOT] ?? crypto.randomUUID())
  const currentPhase = useRef(phase)
  const desired = useRef<'query' | 'results'>(phase === 'results' ? 'results' : 'query')
  const available = useRef(!!state.result?.items.length)
  useEffect(() => { available.current = !!state.result?.items.length }, [state.result])
  useEffect(() => { currentPhase.current = phase }, [phase])
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const waiting = useRef<(() => void) | null>(null)
  const cancel = useCallback(() => { waiting.current?.(); waiting.current = null; if (timer.current !== null) clearTimeout(timer.current); timer.current = null }, [])
  // Restored results need an explicit base entry too. Never remove markers on
  // effect cleanup: StrictMode replays cleanup, and nested entries copy this state.
  useLayoutEffect(() => {
    const next = { ...window.history.state, [HISTORY_SLOT]: owner.current,
      [RESULT_SLOT]: window.history.state?.[RESULT_SLOT] ?? currentPhase.current === 'results' }
    if (currentPhase.current === 'results') next[HISTORY_KEY] = owner.current
    else delete next[HISTORY_KEY]
    window.history.replaceState(next, '', window.location.href)
  }, [])
  const move = useCallback((target: 'query' | 'results', fromHistory = false) => {
    if (desired.current === target) return
    cancel()
    desired.current = target
    const marker = window.history.state?.[HISTORY_KEY]
    if (!fromHistory && target === 'results' && marker !== owner.current) {
      const next = { ...window.history.state, [HISTORY_KEY]: owner.current, [HISTORY_SLOT]: owner.current, [RESULT_SLOT]: true }
      if (window.history.state?.[HISTORY_SLOT] === owner.current && window.history.state?.[RESULT_SLOT]) window.history.replaceState(next, '', window.location.href)
      else window.history.pushState(next, '', window.location.href)
    }
    if (!fromHistory && target === 'query' && marker === owner.current) {
      const next = { ...window.history.state }; delete next[HISTORY_KEY]
      window.history.replaceState(next, '', window.location.href)
    }
    waiting.current = afterLayerExits(() => {
      waiting.current = null
      const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
      currentPhase.current = reduced ? target : target === 'query' ? 'toQuery' : 'toResults'
      setPhase(currentPhase.current)
      if (!reduced) timer.current = setTimeout(() => { currentPhase.current = target; setPhase(target); timer.current = null }, 980)
    })
  }, [cancel])
  useEffect(() => {
    const version = state.result?.version ?? null
    if (version === seen.current) return
    seen.current = version
    if (!state.result || state.result.submittedRevision !== state.revision || !state.result.items.length) return
    const frame = setTimeout(() => move('results'), 0)
    return () => clearTimeout(frame)
  }, [state.result, state.revision, move])
  useEffect(() => cancel, [cancel])
  useEffect(() => {
    if (!state.newQuerySnapshot) return
    const expiry = setTimeout(() => dispatch({ type: 'expireNewQueryUndo' }), 8000)
    return () => clearTimeout(expiry)
  }, [state.newQuerySnapshot, dispatch])
  useEffect(() => {
    const stageOwner = owner.current
    const pop = () => {
      const entry = window.history.state
      // A missing marker on a foreign or router entry says nothing about this
      // workspace. Only explicitly owned stage entries may switch its phase.
      if (entry?.[HISTORY_SLOT] !== stageOwner) return
      if (entry[HISTORY_KEY] === stageOwner && !available.current) return
      move(entry[HISTORY_KEY] === stageOwner ? 'results' : 'query', true)
    }
    window.addEventListener('popstate', pop)
    return () => {
      window.removeEventListener('popstate', pop)
    }
  }, [move])
  return { phase, transitionLocked: phase === 'toResults' || phase === 'toQuery',
    returnToQuery: () => move('query'),
    startNewQuery: () => { move('query'); dispatch({ type: 'startNewQuery' }) },
    undoNewQuery: () => { dispatch({ type: 'undoNewQuery' }); move('results') },
    restartAll: () => { move('query'); dispatch({ type: 'restartAll' }) } }
}
