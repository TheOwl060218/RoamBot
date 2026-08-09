import { describe, expect, it, vi } from 'vitest'

import { startSmoothScrollTo } from '../src/features/search/scrolling'

describe('startSmoothScrollTo', () => {
  it('moves through intermediate positions before reaching the target', () => {
    const frames: FrameRequestCallback[] = []
    const requestAnimationFrame = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      frames.push(callback)
      return frames.length
    })
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    const originalScrollY = Object.getOwnPropertyDescriptor(window, 'scrollY')
    Object.defineProperty(window, 'scrollY', { configurable: true, value: 400 })
    const target = document.createElement('section')
    const header = document.createElement('header')
    header.className = 'shell-header'
    document.body.append(header)
    const onComplete = vi.fn()
    vi.spyOn(header, 'getBoundingClientRect').mockReturnValue({
      top: 0,
      left: 0,
      right: 0,
      bottom: 92,
      width: 0,
      height: 92,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    })
    vi.spyOn(target, 'getBoundingClientRect').mockReturnValue({
      top: 300,
      left: 0,
      right: 0,
      bottom: 0,
      width: 0,
      height: 0,
      x: 0,
      y: 300,
      toJSON: () => ({}),
    })

    try {
      startSmoothScrollTo(() => target, onComplete)
      for (const timestamp of [0, 16, 32, 132, 292, 552]) {
        const frame = frames.shift()
        expect(frame).toBeTypeOf('function')
        frame!(timestamp)
      }

      const positions = scrollTo.mock.calls.map(([options]) => Number((options as ScrollToOptions).top))
      expect(new Set(positions).size).toBeGreaterThan(2)
      expect(positions.at(-1)).toBeCloseTo(592, 0)
      expect(onComplete).toHaveBeenCalledTimes(1)
    } finally {
      header.remove()
      requestAnimationFrame.mockRestore()
      scrollTo.mockRestore()
      if (originalScrollY) Object.defineProperty(window, 'scrollY', originalScrollY)
    }
  })
})
