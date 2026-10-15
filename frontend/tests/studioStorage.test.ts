import { expect, it } from 'vitest'
import { createStudioState } from '../src/features/studio/studioState'
import { loadStudioState, saveStudioState } from '../src/features/studio/studioStorage'
import { saveSearchResult, saveTravelDraft } from '../src/features/search/formState'
import { studioResponse } from './fixtures/studio'

it('rejects stored score values that would crash detail rendering', () => {
  const s = createStudioState()
  const item = { ...studioResponse.items[0], score: { ...studioResponse.items[0].score, popularity: 'broken' } }
  sessionStorage.setItem('roambot.studio.session.v1', JSON.stringify({ version: 1, draft: s.draft, result: {
    version: 1, mode: 'recommendation', items: [item], source_state: studioResponse.source_state, generated_at: studioResponse.generated_at, submittedRevision: 0,
  } }))
  expect(loadStudioState().result).toBeNull()
})

it('ignores plausible but malformed stored results and draft enums', () => {
  const draft = createStudioState().draft
  sessionStorage.setItem('roambot.studio.session.v1', JSON.stringify({ version: 1, draft, result: { items: [{ destination: { provider_id: 'x' } }] } }))
  expect(loadStudioState().result).toBeNull()
  sessionStorage.setItem('roambot.studio.session.v1', JSON.stringify({ version: 1, draft: { ...draft, sceneryTypes: ['invented'] } }))
  expect(loadStudioState().draft.sceneryTypes).toEqual([])
})
it('strips signed facts recursively from optional continuity', () => {
  const s = createStudioState()
  s.result = { version: 1, mode: 'recommendation', items: studioResponse.items, source_state: studioResponse.source_state, generated_at: studioResponse.generated_at, queryRequest: null, submittedRevision: 0, historyId: 'h', historyOwner: 'private-owner', assistantContext: 'signed-secret' }
  saveStudioState(s)
  const stored = sessionStorage.getItem('roambot.studio.session.v1')!
  expect(stored).not.toContain('signed-secret')
  expect(stored).not.toContain('private-owner')
  expect(loadStudioState().result?.assistantContext).toBeUndefined()
  expect(loadStudioState().result?.historyOwner).toBeNull()
})

it('drops malformed saved query metadata while retaining usable destination cards', () => {
  const s = createStudioState()
  sessionStorage.setItem('roambot.studio.session.v1', JSON.stringify({ version: 1, draft: s.draft, result: {
    version: 1, mode: 'recommendation', ...studioResponse, submittedRevision: 0,
    queryRequest: { companion_origins: [], start_date: { broken: true }, end_date: 'bad' },
  } }))
  const restored = loadStudioState()
  expect(restored.result?.items).toHaveLength(4)
  expect(restored.result?.queryRequest).toBeNull()
})

it('restores legacy draft without secret context and tolerates corruption', () => {
  sessionStorage.clear()
  const state = createStudioState()
  saveTravelDraft({ ...state.draft, mainOrigin: '苏州站' })
  expect(loadStudioState().draft.mainOrigin).toBe('苏州站')
  state.messages = [{ role: 'user', content: 'private', id: '1' }]
  saveStudioState(state)
  const saved = sessionStorage.getItem('roambot.studio.session.v1')!
  expect(saved).not.toContain('assistantContext')
  expect(saved).not.toContain('assistant_context')
  saveSearchResult({ assistant_context: 'secret', nested: { assistantContext: 'secret' } })
  expect(sessionStorage.getItem('roambot.session.search-result.v1')).not.toContain('secret')
  sessionStorage.setItem('roambot.studio.session.v1', '{')
  expect(() => loadStudioState()).not.toThrow()
})
