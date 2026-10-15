import { expect, it } from 'vitest'
import { createStudioState, studioReducer, applyAssistantPatch, buildStudioRequest } from '../src/features/studio/studioState'
import { projectConditionCards, projectResultRail } from '../src/features/studio/conditionProjection'

it('starts empty and updates semantic cards instead of duplicating them', () => {
  const state = createStudioState()
  expect(projectConditionCards(state)).toEqual([])
  state.draft = applyAssistantPatch(state.draft, { main_origin: '苏州站', scenery_query: '安静的湖边', scenery_types: ['lake'], scenery_keywords: ['湖泊'] })
  const first = projectConditionCards(state)
  expect(first.map(card => card.id)).toEqual(['mainOrigin', 'sceneryTypes'])
  state.draft = applyAssistantPatch(state.draft, { scenery_query: '热闹的湖边' })
  expect(projectConditionCards(state).map(card => card.id)).toEqual(first.map(card => card.id))
  expect(projectConditionCards(state)[1].value).toBe('热闹的湖边')
})

it('region-only request stays compatible and uses no distance restriction', () => {
  const s = createStudioState()
  s.draft = { ...s.draft, mainOrigin: '苏州站', startDate: '2026-10-11', endDate: '2026-10-11', destinationRegions: ['310000'] }
  expect(buildStudioRequest(s, '2026-10-11').max_distance_km).toBe(500)
  expect(projectResultRail(projectConditionCards(s)).length).toBeLessThanOrEqual(5)
})

it('free preference can search without forcing a six-category selection', () => {
  const s = createStudioState()
  s.draft = { ...s.draft, mainOrigin: '苏州站', startDate: '2026-10-13', endDate: '2026-10-13',
    sceneryTypes: [], sceneryQuery: '适合放空的观景点', sceneryKeywords: ['观景'] }
  const request = buildStudioRequest(s, '2026-10-12')
  expect(request).toMatchObject({ scenery_query: '适合放空的观景点', scenery_keywords: ['观景'] })
  expect(s.draft.sceneryTypes).toEqual([])
})

it('new query preserves team mode while full restart clears it and undo restores query', () => {
  let s = studioReducer(createStudioState(), { type: 'enterTeamPickMode' })
  s = studioReducer(s, { type: 'edit', draft: { ...s.draft, mainOrigin: '苏州站' } })
  const fresh = studioReducer(s, { type: 'startNewQuery' })
  expect(fresh.draft.mainOrigin).toBe('')
  expect(fresh.teamPick.active).toBe(true)
  expect(studioReducer(fresh, { type: 'undoNewQuery' }).draft.mainOrigin).toBe('苏州站')
  expect(studioReducer(s, { type: 'restartAll' }).teamPick.active).toBe(false)
})
