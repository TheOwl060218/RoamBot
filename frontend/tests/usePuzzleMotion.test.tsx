import { renderHook } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { createStudioState } from '../src/features/studio/studioState'
import { usePuzzleMotion } from '../src/features/studio/usePuzzleMotion'

it('keeps real condition buttons stationary and restores their face when a move is interrupted', () => {
  const fixture = document.createElement('div')
  fixture.innerHTML = '<div class="studio-query-page"><div data-condition-id="mainOrigin"><button>出发地</button></div></div><div class="studio-composer"></div>'
  document.body.append(fixture)
  const piece = fixture.querySelector<HTMLElement>('[data-condition-id]')!
  piece.getBoundingClientRect = () => new DOMRect(100, 100, 200, 116)
  const cancel = vi.fn()
  const animation = { cancel, playState: 'running', finished: new Promise(() => undefined) } as unknown as Animation
  const animate = vi.fn<(frames: Keyframe[] | PropertyIndexedKeyframes | null, timing?: number | KeyframeAnimationOptions) => Animation>(() => animation)
  const descriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'animate')
  Object.defineProperty(HTMLElement.prototype, 'animate', { configurable: true, value: animate })
  const state = createStudioState()
  state.draft.mainOrigin = '苏州站'
  const view = renderHook(({ value }) => usePuzzleMotion(value, 'query'), { initialProps: { value: state } })
  try {
    const firstFace = document.querySelector<HTMLElement>('.puzzle-condition-face')!
    expect(firstFace.inert).toBe(true)
    expect(firstFace.getAttribute('aria-hidden')).toBe('true')
    expect(animate.mock.contexts[0]).toBe(firstFace)
    expect(piece.style.transform).toBe('')
    firstFace.getBoundingClientRect = () => new DOMRect(100, 70, 200, 116)
    view.rerender({ value: { ...state, revision: state.revision + 1 } })
    expect(firstFace.isConnected).toBe(false)
    expect(cancel).toHaveBeenCalledOnce()
    expect(animate.mock.calls.at(-1)?.[0]).toEqual([
      { transform: 'translate3d(0px,-30px,0)' },
      { transform: 'translate3d(0,0,0)' },
    ])
    expect(piece.getBoundingClientRect().y).toBe(100)
    view.unmount()
    expect(piece.style.opacity).toBe('')
    expect(document.querySelector('.puzzle-condition-face')).toBeNull()
  } finally {
    view.unmount()
    fixture.remove()
    if (descriptor) Object.defineProperty(HTMLElement.prototype, 'animate', descriptor)
    else Reflect.deleteProperty(HTMLElement.prototype, 'animate')
  }
})
