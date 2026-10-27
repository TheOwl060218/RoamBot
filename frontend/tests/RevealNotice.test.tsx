import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { useRef } from 'react'
import { RevealNotice } from '../src/components/RevealNotice'
import { isRevealVisible, useRevealNotice } from '../src/components/useRevealNotice'

function rect(top: number, bottom: number, left = 10, right = 200): DOMRect {
  return { top, bottom, left, right, x: left, y: top, width: right - left, height: bottom - top, toJSON: () => ({}) }
}
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

test('detects page and scrolling-container clipping without requiring a whole long table to fit', () => {
  const parent = document.createElement('div'), target = document.createElement('div')
  parent.style.overflowY = 'auto'
  parent.append(target); document.body.append(parent)
  vi.spyOn(parent, 'getBoundingClientRect').mockReturnValue(rect(100, 300))
  const box = vi.spyOn(target, 'getBoundingClientRect')
  box.mockReturnValue(rect(320, 900))
  expect(isRevealVisible(target)).toBe(false)
  box.mockReturnValue(rect(150, 1200))
  expect(isRevealVisible(target)).toBe(true)
  box.mockReturnValue(rect(-100, 1200))
  expect(isRevealVisible(target)).toBe(false)
  parent.remove()
})

function Harness() {
  const target = useRef<HTMLDivElement>(null)
  const { notice, notify, clear } = useRevealNotice()
  return <><div ref={target} /><button onClick={() => notify(target.current, '已展开，在下方查看')}>展开</button>
    <button onClick={clear}>收起</button><RevealNotice notice={notice} /></>
}
test('offscreen notice expires after two seconds and reopening restarts its lifetime without stacking', () => {
  vi.useFakeTimers()
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(rect(2000, 2100))
  render(<Harness />)
  fireEvent.click(screen.getByText('展开'))
  expect(screen.getAllByRole('status')).toHaveLength(1)
  act(() => vi.advanceTimersByTime(1500))
  fireEvent.click(screen.getByText('展开'))
  act(() => vi.advanceTimersByTime(600))
  expect(screen.getByRole('status')).toHaveTextContent('在下方查看')
  act(() => vi.advanceTimersByTime(1400))
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  fireEvent.click(screen.getByText('展开'))
  fireEvent.click(screen.getByText('收起'))
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})
test('visible content does not produce a notice', () => {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(rect(50, 150))
  render(<Harness />)
  fireEvent.click(screen.getByText('展开'))
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})
