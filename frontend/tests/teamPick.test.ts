import { expect, it } from 'vitest'
import { createStudioState, studioReducer } from '../src/features/studio/studioState'
import { studioResponse } from './fixtures/studio'
import type { StudioState } from '../src/features/studio/types'
const batch = { version: 1, mode: 'recommendation' as const, items: studioResponse.items, source_state: studioResponse.source_state, generated_at: 'now', queryRequest: null, submittedRevision: 0, historyId: 'h', historyOwner: 'owner' }
it('keeps a shortlist across new query but clears it for a new trusted batch', () => {
  let state: StudioState = { ...createStudioState(), result: batch }
  state = studioReducer(state, { type: 'enterTeamPickMode' })
  state = studioReducer(state, { type: 'toggleCandidate', id: 'place-0' })
  expect(state.teamPick.candidateItems?.[0].destination.provider_id).toBe('place-0')
  state = studioReducer(state, { type: 'startNewQuery' })
  expect(state.teamPick.candidateIds).toEqual(['place-0'])
  state = studioReducer(state, { type: 'queryStarted', requestId: 'q' })
  state = studioReducer(state, { type: 'querySucceeded', requestId: 'q', revision: state.revision, result: { ...batch, version: 2, submittedRevision: state.revision } })
  expect(state.teamPick.active).toBe(true)
  expect(state.teamPick.candidateIds).toEqual([])
  expect(state.teamPick.batchVersion).toBe(2)
  expect(state.queryStatus).toContain('同行清单已清空')
})
it('does not place evaluated places into the team shortlist', () => {
  let state: StudioState = { ...createStudioState(), result: { ...batch, mode: 'place_evaluation' } }
  state = studioReducer(state, { type: 'enterTeamPickMode' })
  state = studioReducer(state, { type: 'toggleCandidate', id: 'place-0' })
  expect(state.teamPick.candidateIds).toEqual([])
  expect(state.selection).toEqual([])
})
it('retains current selected places when a refreshed batch contains both, with fresh snapshots', () => {
  let state: StudioState = { ...createStudioState(), result: batch }
  state = studioReducer(state, { type: 'enterTeamPickMode' })
  for (const id of ['place-0', 'place-1']) state = studioReducer(state, { type: 'toggleCandidate', id })
  state = studioReducer(state, { type: 'queryStarted', requestId: 'refresh' })
  const refreshed = { ...batch, version: 2, items: batch.items.map(item => ({ ...item, explanation: '新推荐' })) }
  state = studioReducer(state, { type: 'querySucceeded', requestId: 'refresh', revision: state.revision, result: refreshed })
  expect(state.selection).toEqual(['place-0', 'place-1'])
  expect(state.teamPick.candidateIds).toEqual(['place-0', 'place-1'])
  expect(state.teamPick.candidateItems?.[0].explanation).toBe('新推荐')
})
