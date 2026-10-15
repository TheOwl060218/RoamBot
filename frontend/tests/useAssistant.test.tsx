import { act, renderHook, waitFor } from '@testing-library/react'
import { useReducer } from 'react'
import { beforeEach, expect, it, vi } from 'vitest'
import { ApiError, apiClient } from '../src/api/client'
import { ACCOUNT_DIALOG_REQUEST_EVENT } from '../src/app/accountDialog'
import { useAssistant } from '../src/features/studio/useAssistant'
import { createStudioState, studioReducer } from '../src/features/studio/studioState'
import { studioResponse } from './fixtures/studio'
beforeEach(() => vi.restoreAllMocks())

it.each([401, 429])('distinguishes authentication failure from AI availability (%s)', async status => {
  vi.spyOn(apiClient, 'post').mockRejectedValue(new ApiError(status, status === 401 ? 'authentication_required' : 'assistant_unavailable', 'failed'))
  const requested = vi.fn()
  window.addEventListener(ACCOUNT_DIALOG_REQUEST_EVENT, requested)
  try {
    const { result } = renderHook(() => {
      const [state, dispatch] = useReducer(studioReducer, undefined, createStudioState)
      return { state, assistant: useAssistant(state, dispatch) }
    })
    await act(async () => { await expect(result.current.assistant.send('苏州10月11日')).rejects.toThrow() })
    expect(result.current.state.messages.some(m => m.content === '苏州10月11日')).toBe(true)
    expect(result.current.state.aiStatus).toContain(status === 401 ? '登录' : 'AI暂不可用')
    expect(requested).toHaveBeenCalledTimes(status === 401 ? 1 : 0)
  } finally { window.removeEventListener(ACCOUNT_DIALOG_REQUEST_EVENT, requested) }
})

it('ignores an answer started before a new result batch arrives', async () => {
  let complete!: (value: unknown) => void
  vi.spyOn(apiClient, 'post').mockImplementation(() => new Promise(resolve => { complete = resolve }))
  const { result } = renderHook(() => { const [state, dispatch] = useReducer(studioReducer, undefined, createStudioState); return { state, dispatch, assistant: useAssistant(state, dispatch) } })
  let task!: Promise<void>
  act(() => { task = result.current.assistant.send('苏州站') })
  act(() => {
    result.current.dispatch({ type: 'queryStarted', requestId: 'q' })
    result.current.dispatch({ type: 'querySucceeded', requestId: 'q', revision: 0, result: {
      version: 1, mode: 'recommendation', ...studioResponse, queryRequest: null, submittedRevision: 0, historyId: null, historyOwner: null,
    } })
  })
  await act(async () => { complete({ revision: 0, reply: 'old answer', patch: { main_origin: '苏州站' }, source: 'demo' }); await task })
  expect(result.current.state.draft.mainOrigin).toBe('')
  expect(result.current.state.messages.some(m => m.content === 'old answer')).toBe(false)
  expect(result.current.state.aiRequestId).toBeNull()
})

it('retries without a stale assistant context after backend restart', async () => {
  const post = vi.spyOn(apiClient, 'post')
    .mockRejectedValueOnce(new ApiError(409, 'assistant_context_expired', 'stale'))
    .mockResolvedValueOnce({ revision: 0, reply: 'ok', patch: { main_origin: '苏州站' }, source: 'demo' })
  const { result } = renderHook(() => { const [state, dispatch] = useReducer(studioReducer, undefined, createStudioState); return { state, dispatch, assistant: useAssistant(state, dispatch) } })
  act(() => {
    result.current.dispatch({ type: 'queryStarted', requestId: 'q' })
    result.current.dispatch({ type: 'querySucceeded', requestId: 'q', revision: 0, result: {
      version: 1, mode: 'recommendation', ...studioResponse, queryRequest: null, submittedRevision: 0, historyId: null, historyOwner: null, assistantContext: 'stale-signature',
    } })
  })
  let task!: Promise<void>
  act(() => { task = result.current.assistant.send('明天出发') })
  await act(async () => { await task })
  expect(post).toHaveBeenCalledTimes(2)
  expect(post.mock.calls[0][1]).toMatchObject({ assistant_context: 'stale-signature' })
  expect(post.mock.calls[1][1]).not.toHaveProperty('assistant_context')
  expect(result.current.state.draft.mainOrigin).toBe('苏州站')
  expect(result.current.state.aiRequestId).toBeNull()
})

it('assistant patch never submits recommendations and stale patch does not overwrite edits', async () => {
  let complete!: (value: unknown) => void
  const post = vi.spyOn(apiClient, 'post').mockImplementation(() => new Promise(resolve => { complete = resolve }))
  const { result } = renderHook(() => { const [state, dispatch] = useReducer(studioReducer, undefined, createStudioState); return { state, dispatch, assistant: useAssistant(state, dispatch) } })
  let task!: Promise<void>
  act(() => { task = result.current.assistant.send('苏州站') })
  act(() => result.current.dispatch({ type: 'edit', draft: { ...result.current.state.draft, mainOrigin: '上海站' } }))
  await act(async () => { complete({ revision: 0, reply: 'ok', patch: { main_origin: '苏州站' }, source: 'demo' }); await task })
  await waitFor(() => expect(result.current.state.draft.mainOrigin).toBe('上海站'))
  expect(post.mock.calls.map(c => c[0])).toEqual(['/assistant/turns'])
  expect(result.current.state.aiRequestId).toBeNull()
})
