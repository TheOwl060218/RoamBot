import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { StudioMenu } from '../src/features/studio/StudioMenu'
it('makes manual conditions available before an AI request and opens the chosen editor', () => {
  const onEdit = vi.fn()
  render(<StudioMenu onEdit={onEdit} onNew={vi.fn()} onClear={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: '更多功能' }))
  fireEvent.click(screen.getByRole('button', { name: '手动填写条件' }))
  for (const name of ['出发地', '日期', '想找的地方', '目的地范围', '同行出发地', '推荐偏好']) {
    expect(screen.getByRole('button', { name, exact: true })).toBeVisible()
  }
  fireEvent.click(screen.getByRole('button', { name: '出发地', exact: true }))
  expect(onEdit).toHaveBeenCalledWith('mainOrigin')
  expect(screen.queryByRole('dialog')).toBeNull()
})
it('offers three clear functions and closes on an outside press', () => {
  render(<StudioMenu onEdit={vi.fn()} onNew={vi.fn()} onClear={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: '更多功能' }))
  expect(screen.getByRole('button', { name: '评估指定地点' })).toBeVisible()
  expect(screen.getByRole('button', { name: '从收藏中选择' })).toBeVisible()
  expect(screen.getByRole('button', { name: '发起同行挑选' })).toBeVisible()
  fireEvent.pointerDown(screen.getByTestId('overlay-backdrop'))
  fireEvent.pointerUp(screen.getByTestId('overlay-backdrop'))
  expect(screen.queryByRole('dialog')).toBeNull()
})
