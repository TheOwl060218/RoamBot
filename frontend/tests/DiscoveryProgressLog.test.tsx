import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DiscoveryProgressLog } from '../src/features/discovery/DiscoveryProgressLog'

afterEach(() => vi.unstubAllGlobals())

it('starts empty, follows new lines and preserves the reading position until returning to the bottom', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
  const scrollTo = vi.fn()
  const original = HTMLElement.prototype.scrollTo
  HTMLElement.prototype.scrollTo = scrollTo
  try {
    const view = render(<DiscoveryProgressLog lines={[]} />)
    const log = screen.getByRole('log', { name: '本次查找过程' })
    expect(log).toBeEmptyDOMElement()
    Object.defineProperty(log, 'clientHeight', { configurable: true, value: 86 })
    let height = 86
    Object.defineProperty(log, 'scrollHeight', { configurable: true, get: () => height })
    view.rerender(<DiscoveryProgressLog lines={['一句', '二句', '三句']} />)
    height = 112
    view.rerender(<DiscoveryProgressLog lines={['一句', '二句', '三句', '四句']} />)
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 26, behavior: 'smooth' })
    log.scrollTop = 26; fireEvent.scroll(log)
    fireEvent.wheel(log, { deltaY: -26 })
    log.scrollTop = 0; fireEvent.scroll(log)
    const calls = scrollTo.mock.calls.length
    height = 138
    view.rerender(<DiscoveryProgressLog lines={['一句', '二句', '三句', '四句', '五句']} />)
    expect(scrollTo).toHaveBeenCalledTimes(calls)
    expect(log).toHaveTextContent('一句')
    log.scrollTop = 52; fireEvent.scroll(log)
    height = 164
    view.rerender(<DiscoveryProgressLog lines={['一句', '二句', '三句', '四句', '五句', '六句']} />)
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 78, behavior: 'smooth' })
  } finally { HTMLElement.prototype.scrollTo = original }
})

it('honors reduced motion when following new progress', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true }))
  const scrollTo = vi.fn()
  const original = HTMLElement.prototype.scrollTo
  HTMLElement.prototype.scrollTo = scrollTo
  try {
    render(<DiscoveryProgressLog lines={['真实进展']} />)
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, behavior: 'instant' })
  } finally { HTMLElement.prototype.scrollTo = original }
})
