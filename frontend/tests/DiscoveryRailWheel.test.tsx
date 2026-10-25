import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { DiscoveryRail } from '../src/features/discovery/DiscoveryRail'

it('leaves vertical wheel scrolling to the page when the rail is clipped below the chat area', () => {
  render(<div data-command-scroll><DiscoveryRail><article>地点</article></DiscoveryRail></div>)
  const rail = screen.getByRole('region', { name: '推荐去处' })
  const browse = rail.closest('[data-command-scroll]')!
  Object.defineProperty(rail, 'clientWidth', { value: 300 })
  Object.defineProperty(rail, 'scrollWidth', { value: 900 })
  Object.defineProperty(browse, 'clientHeight', { value: 300 })
  Object.defineProperty(browse, 'scrollHeight', { value: 600 })
  vi.spyOn(browse, 'getBoundingClientRect').mockReturnValue({ top: 100, bottom: 400 } as DOMRect)
  const bounds = vi.spyOn(rail, 'getBoundingClientRect').mockReturnValue({ top: 200, bottom: 530 } as DOMRect)
  const clipped = new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaY: 60 })
  fireEvent(rail, clipped)
  expect(clipped.defaultPrevented).toBe(false)
  expect(rail.scrollLeft).toBe(0)
  bounds.mockReturnValue({ top: 110, bottom: 390 } as DOMRect)
  const visible = new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaY: 60 })
  fireEvent(rail, visible)
  expect(visible.defaultPrevented).toBe(true)
  expect(rail.scrollLeft).toBe(60)
})
