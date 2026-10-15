import { act, fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { Composer } from '../src/features/studio/Composer'

it('preserves the next message typed while an earlier message is sending', async () => {
  let finish!: () => void
  render(<Composer busy={false} onSend={() => new Promise<void>(resolve => { finish = resolve })} />)
  const input = screen.getByRole('textbox', { name: '继续补充条件' })
  fireEvent.change(input, { target: { value: '苏州站' } })
  fireEvent.keyDown(input, { key: 'Enter' })
  fireEvent.change(input, { target: { value: '明天出发' } })
  await act(async () => { finish() })
  expect(input).toHaveValue('明天出发')
})

it('does not send Enter during composition or send twice in flight', () => {
  const onSend = vi.fn(() => new Promise<void>(() => {}))
  render(<Composer busy={false} onSend={onSend} />)
  const input = screen.getByRole('textbox', { name: '继续补充条件' })
  fireEvent.change(input, { target: { value: '明天出发' } })
  fireEvent.compositionStart(input)
  fireEvent.keyDown(input, { key: 'Enter', isComposing: true })
  expect(onSend).not.toHaveBeenCalled()
  fireEvent.compositionEnd(input)
  fireEvent.keyDown(input, { key: 'Enter' })
  fireEvent.keyDown(input, { key: 'Enter' })
  expect(onSend).toHaveBeenCalledTimes(1)
  expect(input).toBeVisible()
})
