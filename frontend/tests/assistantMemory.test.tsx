import { act, renderHook } from '@testing-library/react'
import { useReducer } from 'react'
import { expect, it, vi } from 'vitest'
import { createStudioState, studioReducer } from '../src/features/studio/studioState'
import { loadStudioState, saveStudioState } from '../src/features/studio/studioStorage'
import { useAssistant } from '../src/features/studio/useAssistant'
import { requestAssistantTurn } from '../src/features/studio/assistantClient'

vi.mock('../src/features/studio/assistantClient', () => ({ requestAssistantTurn: vi.fn() }))
const pending = { pending_date_request: { duration_days: 3 } }

it('retains pending days on an empty patch and sends them with the next turn', async () => {
  const api = vi.mocked(requestAssistantTurn)
  api.mockResolvedValueOnce({ revision: 0, reply: '哪天出发？', source: 'live', conversation_state: pending })
  api.mockResolvedValueOnce({ revision: 1, reply: '已补全日期', source: 'live', conversation_state: { pending_date_request: null },
    patch: { start_date: '2026-10-15', end_date: '2026-10-17' } })
  const { result } = renderHook(() => {
    const [state, dispatch] = useReducer(studioReducer, undefined, createStudioState)
    return { state, ...useAssistant(state, dispatch) }
  })
  await act(async () => { await result.current.send('待三天') })
  expect(result.current.state.conversationState).toEqual(pending)
  expect(result.current.state.draft.startDate).toBe('')
  await act(async () => { await result.current.send('后天走') })
  expect(api.mock.calls.at(-1)?.[0].conversation_state).toEqual(pending)
  expect(result.current.state.draft.endDate).toBe('2026-10-17')
  expect(result.current.state.conversationState.pending_date_request).toBeNull()
})

it('manual date changes and explicit reset discard pending date fragments', () => {
  const initial = { ...createStudioState(), conversationState: pending }
  const unrelated = studioReducer(initial, { type: 'edit', draft: { ...initial.draft, mainOrigin: '合肥' } })
  expect(unrelated.conversationState).toEqual(pending)
  const changed = studioReducer(initial, { type: 'edit', draft: { ...initial.draft, startDate: '2026-10-15', endDate: '2026-10-15' } })
  expect(changed.conversationState.pending_date_request).toBeNull()
  for (const action of [{ type: 'removeCondition', key: 'dates' }, { type: 'clearConversation' }, { type: 'startNewQuery' }, { type: 'restartAll' }] as const) {
    expect(studioReducer(initial, action).conversationState.pending_date_request).toBeNull()
  }
})

it('late replies and failed requests cannot overwrite pending dates', () => {
  const initial = { ...createStudioState(), conversationState: pending, revision: 2, aiRequestId: 'request' }
  const late = studioReducer(initial, { type: 'applyAssistant', requestId: 'request', revision: 1,
    response: { revision: 1, reply: 'old', source: 'live', conversation_state: { pending_date_request: null } } })
  expect(late.conversationState).toEqual(pending)
  expect(studioReducer(initial, { type: 'aiFailed', requestId: 'request', message: 'offline' }).conversationState).toEqual(pending)
})

it('reload retains bounded pending dates without requiring stored chat', () => {
  const state = { ...createStudioState(), conversationState: pending }
  saveStudioState(state)
  expect(loadStudioState().conversationState).toEqual(pending)
  const saved = JSON.parse(sessionStorage.getItem('roambot.studio.session.v1')!)
  saved.conversationState = { pending_date_request: { duration_days: 900 } }
  sessionStorage.setItem('roambot.studio.session.v1', JSON.stringify(saved))
  expect(loadStudioState().conversationState.pending_date_request).toBeNull()
})
