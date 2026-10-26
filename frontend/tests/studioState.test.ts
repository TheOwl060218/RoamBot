import { describe, expect, it } from 'vitest'
import { createStudioState, studioReducer, applyAssistantPatch, buildStudioRequest } from '../src/features/studio/studioState'
import { studioResponse } from './fixtures/studio'

describe('studio state', () => {
  it('associates a result answer with its batch instead of reusing query-page copy', () => {
    const state = createStudioState()
    state.result = { version: 7, mode: 'recommendation', items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', submittedRevision: 0, historyId: null, historyOwner: null, queryRequest: null }
    state.aiRequestId = 'answer'
    const next = studioReducer(state, { type: 'applyAssistant', requestId: 'answer', revision: 0, resultVersion: 7, response: { revision: 0, reply: '第一个地点距离较短。', source: 'demo' } })
    expect(next.messages.at(-1)?.resultVersion).toBe(7)
  })
  it('restores a new-query snapshot without falsely marking unchanged results dirty', () => {
    const s = createStudioState()
    s.result = { version: 1, mode: 'recommendation', items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', submittedRevision: 0, historyId: 'h', historyOwner: 'owner', queryRequest: null }
    const next = studioReducer(studioReducer(s, { type: 'startNewQuery' }), { type: 'undoNewQuery' })
    expect(next.result?.submittedRevision).toBe(next.revision)
    expect(next.queryRequestId).toBeNull()
    expect(next.result?.historyId).toBe('h')
  })
  it('logout invalidates private answer context, history trust and in-flight AI', () => {
    const s = createStudioState()
    s.result = { version: 1, mode: 'recommendation', items: studioResponse.items, source_state: studioResponse.source_state, generated_at: studioResponse.generated_at, submittedRevision: 0, historyId: 'h', historyOwner: 'owner', assistantContext: 'signed', queryRequest: null }
    s.aiRequestId = 'pending'
    const next = studioReducer(s, { type: 'logout' })
    expect(next.result?.historyOwner).toBeNull()
    expect(next.result?.assistantContext).toBeUndefined()
    expect(next.aiRequestId).toBeNull()
    expect(next.result?.items).toEqual(s.result.items)
  })
  it('logout discards an undo snapshot carrying the previous account context', () => {
    const s = createStudioState()
    s.result = { version: 1, mode: 'recommendation', items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', submittedRevision: 0, historyId: 'h', historyOwner: 'old-user', assistantContext: 'private-context', queryRequest: null }
    const next = studioReducer(studioReducer(s, { type: 'startNewQuery' }), { type: 'logout' })
    expect(next.newQuerySnapshot).toBeNull()
    expect(studioReducer(next, { type: 'undoNewQuery' }).result).toBeNull()
  })
  it('keeps existing results dirty and only preserves selected IDs that remain after explicit rerun', () => {
    let s = createStudioState()
    const result = { version: 1, mode: 'recommendation' as const, items: studioResponse.items, source_state: studioResponse.source_state, generated_at: studioResponse.generated_at, submittedRevision: 0, historyId: 'history', historyOwner: 'owner', queryRequest: null }
    s = { ...s, result, selection: ['place-0','place-1'] }
    s = studioReducer(s, { type: 'edit', draft: { ...s.draft, maxDistance: '80' } })
    expect(s.result).toBe(result)
    expect(s.revision).not.toBe(s.result?.submittedRevision)
    s = studioReducer(s, { type: 'queryStarted', requestId: 'q' })
    s = studioReducer(s, { type: 'querySucceeded', requestId: 'q', revision: s.revision, result: { ...result, version: 2, submittedRevision: s.revision } })
    expect(s.selection).toEqual(['place-0','place-1'])
    s = studioReducer(s, { type: 'queryStarted', requestId: 'q2' })
    s = studioReducer(s, { type: 'querySucceeded', requestId: 'q2', revision: s.revision, result: { ...result, version: 3, items: result.items.slice(2), submittedRevision: s.revision } })
    expect(s.selection).toEqual([])
    expect(s.queryStatus).toContain('候选已变化')
  })
  it('rejects stale patches and clears changed address coordinates', () => {
    const before = createStudioState()
    const stale = studioReducer(before, { type: 'applyAssistant', revision: 9, requestId: 'late', response: { revision: 9, patch: { main_origin: '上海站' }, reply: 'x', source: 'demo' } })
    expect(stale.draft).toEqual(before.draft)
    const draft = { ...before.draft, mainOrigin: 'a', mainOriginCoordinate: { longitude: 120, latitude: 31, system: 'gcj02' }, companions: ['b'], companionOriginCoordinates: [{ longitude: 121, latitude: 32, system: 'gcj02' }] }
    const edited = applyAssistantPatch(draft, { main_origin: 'c', companion_origins: [] })
    expect(edited.mainOriginCoordinate).toBeNull()
    expect(edited.companionOriginCoordinates).toEqual([])
    expect(applyAssistantPatch(edited, { main_origin: null }).mainOrigin).toBe('')
  })
  it('requires explicit complete input and rejects dates after midnight', () => {
    const state = createStudioState()
    expect(state.draft.startDate).toBe('')
    expect(() => buildStudioRequest(state, '2026-10-10')).toThrow('出发地')
    state.draft = { ...state.draft, mainOrigin: '苏州站', startDate: '2026-10-10', endDate: '2026-10-10', sceneryTypes: ['lake'] }
    expect(buildStudioRequest(state, '2026-10-10').main_origin).toBe('苏州站')
    expect(() => buildStudioRequest(state, '2026-10-11')).toThrow('日期')
    expect(buildStudioRequest({ ...state, draft: { ...state.draft, destinationRegions: ['310000'], maxDistance: '' } }, '2026-10-10').max_distance_km).toBe(500)
  })
})
