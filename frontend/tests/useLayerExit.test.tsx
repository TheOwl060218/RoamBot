import { render } from '@testing-library/react'
import { useRef } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useLayerExit } from '../src/features/studio/useLayerExit'

function Layer() {
  const root = useRef<HTMLDivElement>(null)
  useLayerExit(root, 'section')
  return <div ref={root} className='test-layer'><section>panel body</section></div>
}

const animateCalls: { target: Element; keyframes: Record<string, string>[] }[] = []

beforeEach(() => {
  animateCalls.length = 0
  vi.spyOn(window, 'getComputedStyle').mockImplementation(
    () => ({ backdropFilter: 'blur(6px)' }) as unknown as CSSStyleDeclaration,
  )
  ;(Element.prototype as { animate?: unknown }).animate = function (
    this: Element,
    keyframes: Record<string, string>[],
  ) {
    animateCalls.push({ target: this, keyframes })
    return { finished: Promise.resolve(), cancel: () => undefined }
  }
})

afterEach(() => {
  vi.restoreAllMocks()
  delete (Element.prototype as { animate?: unknown }).animate
  document.querySelectorAll('[data-exit-snapshot]').forEach(node => node.remove())
})

describe('useLayerExit', () => {
  it('dissolves the veil in place instead of sliding the layer down when no return target exists', () => {
    const { unmount } = render(<Layer />)
    unmount()

    const copy = document.querySelector('[data-exit-snapshot]')
    expect(copy).not.toBeNull()
    const panelCall = animateCalls.find(call => call.target === copy!.querySelector('section'))
    expect(panelCall?.keyframes.at(-1)?.transform).toBe('none')
    const veilCall = animateCalls.find(call => call.keyframes.some(frame => 'backdropFilter' in frame))
    expect(veilCall?.keyframes.at(-1)?.backdropFilter).toBe('blur(0px)')
  })
})
