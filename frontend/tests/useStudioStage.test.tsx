import { act, renderHook } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { useStudioStage } from '../src/features/studio/useStudioStage'
import { createStudioState, studioReducer } from '../src/features/studio/studioState'
import { useReducer } from 'react'
import { studioResponse } from './fixtures/studio'
import { trackLayerExit } from '../src/features/studio/layerMotion'
beforeEach(() => window.history.replaceState({}, '', window.location.href))
it('keeps an explicitly owned result stage on refresh even when its conditions are dirty', () => {
  const state = createStudioState()
  state.revision = 1
  state.result = { version: 1, mode: 'recommendation', items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', queryRequest: null, submittedRevision: 0, historyId: null, historyOwner: null }
  window.history.replaceState({ roambotStudioStageSlot: 'saved-stage', roambotStudioStage: 'saved-stage', roambotStudioResultSlot: true }, '', window.location.href)
  const view = renderHook(() => useStudioStage(state, vi.fn()))
  expect(view.result.current.phase).toBe('results')
})
it('reuses the result-stage history slot on repeated return and recommendation', async () => {
  vi.useFakeTimers()
  const state = createStudioState()
  const view = renderHook(({ value }) => useStudioStage(value, vi.fn()), { initialProps: { value: state } })
  const result = { version: 1, mode: 'recommendation' as const, items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', queryRequest: null, submittedRevision: 0, historyId: null, historyOwner: null }
  view.rerender({ value: { ...state, result } })
  await act(async () => { await vi.advanceTimersByTimeAsync(1100) })
  const count = window.history.length
  act(() => view.result.current.returnToQuery())
  await act(async () => { await vi.advanceTimersByTimeAsync(1100) })
  view.rerender({ value: { ...state, result: { ...result, version: 2 } } })
  await act(async () => { await vi.advanceTimersByTimeAsync(1100) })
  expect(window.history.length).toBe(count)
  view.unmount()
  vi.useRealTimers()
})
it('expires the new-query undo after a short window', async () => {
  vi.useFakeTimers()
  const view = renderHook(() => {
    const [state, dispatch] = useReducer(studioReducer, createStudioState())
    return { state, stage: useStudioStage(state, dispatch) }
  })
  act(() => view.result.current.stage.startNewQuery())
  expect(view.result.current.state.newQuerySnapshot).toBeTruthy()
  await act(async () => { await vi.advanceTimersByTimeAsync(9000) })
  expect(view.result.current.state.newQuerySnapshot).toBeNull()
  vi.useRealTimers()
})
it('reveals valid results, reverses without erasing conditions, and interrupts safely', async () => {
  vi.useFakeTimers()
  const state = createStudioState()
  const dispatch = vi.fn()
  const view = renderHook(({ value }) => useStudioStage(value, dispatch), { initialProps: { value: state } })
  expect(view.result.current.phase).toBe('query')
  const completed = { ...state, result: { version: 1, mode: 'recommendation' as const, items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', queryRequest: null, submittedRevision: 0, historyId: null, historyOwner: null } }
  view.rerender({ value: completed })
  await act(async () => { await vi.advanceTimersByTimeAsync(20) })
  expect(view.result.current.phase).toBe('toResults')
  act(() => view.result.current.returnToQuery())
  await act(async () => { await vi.advanceTimersByTimeAsync(1100) })
  expect(view.result.current.phase).toBe('query')
  expect(dispatch).not.toHaveBeenCalled()
  vi.useRealTimers()
})
it('does not transition to stale results', async () => {
  const state = createStudioState()
  state.revision = 2
  state.result = { version: 1, mode: 'recommendation', items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', queryRequest: null, submittedRevision: 1, historyId: null, historyOwner: null }
  const view = renderHook(() => useStudioStage(state, vi.fn()))
  expect(view.result.current.phase).toBe('query')
})
it('browser back reverses only the result stage, not a nested detail layer', async () => {
  vi.useFakeTimers()
  const state = createStudioState()
  const view = renderHook(({ value }) => useStudioStage(value, vi.fn()), { initialProps: { value: state } })
  const completed = { ...state, result: { version: 1, mode: 'recommendation' as const, items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', queryRequest: null, submittedRevision: 0, historyId: null, historyOwner: null } }
  view.rerender({ value: completed })
  await act(async () => { await vi.advanceTimersByTimeAsync(1100) })
  window.dispatchEvent(new PopStateEvent('popstate'))
  expect(view.result.current.phase).toBe('results')
  const queryEntry = { ...window.history.state }
  delete queryEntry.roambotStudioStage
  window.history.replaceState(queryEntry, '', window.location.href)
  act(() => window.dispatchEvent(new PopStateEvent('popstate')))
  await act(async () => { await vi.advanceTimersByTimeAsync(1100) })
  expect(view.result.current.phase).toBe('query')
  vi.useRealTimers()
})
it('stamps restored results and ignores unowned entries without rewriting them', async () => {
  vi.useFakeTimers()
  const state = createStudioState()
  state.result = { version: 1, mode: 'recommendation', items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', queryRequest: null, submittedRevision: 0, historyId: null, historyOwner: null }
  const view = renderHook(() => useStudioStage(state, vi.fn()))
  expect(window.history.state.roambotStudioStage).toBe(window.history.state.roambotStudioStageSlot)
  window.history.replaceState({ unrelated: true }, '', window.location.href)
  act(() => window.dispatchEvent(new PopStateEvent('popstate')))
  await act(async () => { await vi.advanceTimersByTimeAsync(1100) })
  expect(view.result.current.phase).toBe('results')
  expect(window.history.state).toEqual({ unrelated: true })
  vi.useRealTimers()
})
it('waits for the exiting layer before starting a page slide', async () => {
  vi.useFakeTimers()
  const state = createStudioState()
  state.result = { version: 1, mode: 'recommendation', items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', queryRequest: null, submittedRevision: 0, historyId: null, historyOwner: null }
  const view = renderHook(() => useStudioStage(state, vi.fn()))
  let finish!: () => void
  trackLayerExit(new Promise<void>(resolve => { finish = resolve }))
  act(() => view.result.current.returnToQuery())
  await act(async () => { await vi.advanceTimersByTimeAsync(100) })
  expect(view.result.current.phase).toBe('results')
  await act(async () => { finish(); await vi.advanceTimersByTimeAsync(1100) })
  expect(view.result.current.phase).toBe('query')
  vi.useRealTimers()
})
