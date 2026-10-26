import { expect, test } from 'vitest'
import { planProgress } from '../src/features/plans/planPresentation'
import { workbenchPlan } from './fixtures/workbenchPlan'

test('visible participant votes supply progress when no aggregate is available', () => {
  const plan = workbenchPlan()
  plan.participants = [
    { id: 'owner', nickname: 'owner', role: 'owner', voted: true },
    { id: 'guest', nickname: 'guest', role: 'guest', voted: true },
    { id: 'waiting', nickname: 'waiting', role: 'guest', voted: false },
  ]
  expect(planProgress(plan)).toBe('2/3 人已投票')
  plan.expected_count = 1
  expect(planProgress(plan)).toBe('2 人已参与')
})

test('an explicit aggregate zero is authoritative over the participant fallback', () => {
  const plan = workbenchPlan()
  plan.participants![0].voted = true
  plan.summary = { joined_count: 1, voted_count: 0, complete: false, candidates: [] }
  expect(planProgress(plan)).toBe('0/3 人已投票')
})

test('missing private participants are never inferred from the current member vote', () => {
  const plan = workbenchPlan()
  plan.participants = null
  plan.me!.preferred_id = '0'
  expect(planProgress(plan)).toBe('0/3 人已投票')
})
