import { expect, it } from 'vitest'
import { routeMotion } from '../src/app/routeMotion'
it('uses bounded directions and their inverse instead of multi-page distances', () => {
  expect(routeMotion('/plans')).toEqual({ x: '0px', y: '48px' })
  expect(routeMotion('/favorites')).toEqual({ x: '64px', y: '0px' })
  expect(routeMotion('/history')).toEqual({ x: '-64px', y: '0px' })
  expect(routeMotion('/favorites', true)).toEqual({ x: '-64px', y: '0px' })
})
