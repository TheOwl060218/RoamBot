import { describe, expect, it, vi } from 'vitest'

import { startSmoothScrollInContainer, startSmoothScrollTo } from '../src/features/search/scrolling'

describe('startSmoothScrollInContainer', () => {
  it('finishes with the target aligned to the container after layout shifts', () => {
    const frames: FrameRequestCallback[] = []
    const requestAnimationFrame = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      frames.push(callback)
      return frames.length
    })
    const container = document.createElement('aside')
    const target = document.createElement('section')
    target.style.scrollMarginTop = '24px'
    let targetTop = 500
    Object.defineProperty(container, 'scrollTop', { configurable: true, writable: true, value: 100 })
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue({
      top: 100, left: 0, right: 0, bottom: 700, width: 400, height: 600, x: 0, y: 100, toJSON: () => ({}),
    })
    vi.spyOn(target, 'getBoundingClientRect').mockImplementation(() => ({
      top: targetTop, left: 0, right: 0, bottom: targetTop + 100, width: 400, height: 100, x: 0, y: targetTop, toJSON: () => ({}),
    }))
    const onComplete = vi.fn()

    try {
      startSmoothScrollInContainer(container, () => target, onComplete)
      frames.shift()!(0)
      frames.shift()!(0)
      frames.shift()!(0)
      targetTop = 450
      frames.shift()!(552)

      expect(container.scrollTop).toBeCloseTo(426, 0)
      expect(onComplete).toHaveBeenCalledTimes(1)
    } finally {
      requestAnimationFrame.mockRestore()
    }
  })
})

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
