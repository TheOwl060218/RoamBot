import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { OverlayHost } from '../src/features/studio/OverlayHost'

it('closes on a full outside press but not a drag from inside', () => {
  const close = vi.fn()
  render(<OverlayHost label='编辑条件' onClose={close}><button>保存</button></OverlayHost>)
  const backdrop = screen.getByTestId('overlay-backdrop')
  fireEvent.pointerDown(screen.getByText('保存'))
  fireEvent.pointerUp(backdrop)
  expect(close).not.toHaveBeenCalled()
  fireEvent.pointerDown(backdrop)
  fireEvent.pointerUp(backdrop)
  expect(close).toHaveBeenCalledTimes(1)
})

it('escapes and restores focus without affecting surrounding layout', () => {
  const trigger = document.createElement('button')
  document.body.append(trigger)
  trigger.focus()
  const close = vi.fn()
  const view = render(<OverlayHost label='编辑条件' onClose={close}><input aria-label='文字' /></OverlayHost>)
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
  expect(close).toHaveBeenCalledTimes(1)
  view.unmount()
  expect(trigger).toHaveFocus()
  trigger.remove()
})
