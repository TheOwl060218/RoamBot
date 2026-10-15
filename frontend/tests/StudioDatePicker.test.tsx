import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { StudioDatePicker } from '../src/features/studio/StudioDatePicker'

it('chooses tomorrow without a native date input', () => {
  const change = vi.fn()
  render(<StudioDatePicker start='' end='' onChange={change} today='2026-10-11' />)
  fireEvent.click(screen.getByRole('button', { name: '明天' }))
  expect(change).toHaveBeenCalledWith('2026-10-12', '2026-10-12')
  expect(document.querySelector('input[type=date]')).toBeNull()
})
it('selects and normalizes a custom range within seven days', () => {
  const change = vi.fn()
  render(<StudioDatePicker start='' end='' onChange={change} today='2026-10-11' />)
  fireEvent.click(screen.getByRole('button', { name: '自选日期' }))
  fireEvent.click(screen.getByRole('button', { name: '2026-10-15' }))
  fireEvent.click(screen.getByRole('button', { name: '2026-10-12' }))
  expect(change).toHaveBeenLastCalledWith('2026-10-12', '2026-10-15')
  expect(screen.queryByRole('button', { name: '2026-10-18' })).toBeNull()
})
