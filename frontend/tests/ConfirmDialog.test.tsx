import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { ConfirmDialog } from '../src/app/ConfirmDialog'

it('closes with Escape and restores focus to the invoking control', async () => {
  const user = userEvent.setup()
  const onCancel = vi.fn()
  const { rerender } = render(
    <>
      <button type="button">删除记录</button>
      <ConfirmDialog
        open={false}
        title="删除记录？"
        message="此操作无法撤销。"
        confirmLabel="删除"
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />
    </>,
  )
  const trigger = screen.getByRole('button', { name: '删除记录' })
  trigger.focus()

  rerender(
    <>
      <button type="button">删除记录</button>
      <ConfirmDialog
        open
        title="删除记录？"
        message="此操作无法撤销。"
        confirmLabel="删除"
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />
    </>,
  )

  expect(screen.getByRole('button', { name: '取消' })).toHaveFocus()
  await user.keyboard('{Escape}')
  expect(onCancel).toHaveBeenCalledOnce()
})
