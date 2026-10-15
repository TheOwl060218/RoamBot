import { expect, it } from 'vitest'
import { localSceneryTypes } from '../src/features/studio/localScenery'
it('does not turn excluded scenery or subjective quietness into positive types', () => {
  expect(localSceneryTypes('不要去博物馆，想在湖边散步')).toEqual(['lake', 'park'])
  expect(localSceneryTypes('安静一点，适合摄影')).toEqual([])
})
