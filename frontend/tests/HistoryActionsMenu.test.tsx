import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { HistoryActionsMenu } from '../src/features/history/HistoryActionsMenu'

function view() {
  render(<HistoryActionsMenu historyId='fixture' rerunning={false} rerunDisabled={false}
    onRerun={() => undefined} onDelete={() => undefined} onStatus={() => undefined} />)
}

test('opening the capsule exposes common actions but keeps deletion behind more', async () => {
  view()
  await userEvent.click(screen.getByRole('button', { name: '更多历史操作' }))
  expect(screen.getByRole('toolbar', { name: '历史快捷操作' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '重新查询' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '创建分享' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '删除历史' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '更多操作' }))
  expect(screen.getByRole('button', { name: '删除历史' })).toBeInTheDocument()
})

test('Escape dismisses the capsule and returns focus to its original trigger', async () => {
  view()
  const trigger = screen.getByRole('button', { name: '更多历史操作' })
  await userEvent.click(trigger)
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('toolbar', { name: '历史快捷操作' })).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})

test('deletion still calls the owner confirmation flow only after opening more', async () => {
  const remove = vi.fn()
  render(<HistoryActionsMenu historyId='fixture' rerunning={false} rerunDisabled={false}
    onRerun={() => undefined} onDelete={remove} onStatus={() => undefined} />)
  await userEvent.click(screen.getByRole('button', { name: '更多历史操作' }))
  expect(screen.queryByRole('button', { name: '删除历史' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '更多操作' }))
  await userEvent.click(screen.getByRole('button', { name: '删除历史' }))
  expect(remove).toHaveBeenCalledTimes(1)
})

test('outside clicks dismiss more actions and reopening keeps deletion tucked away', async () => {
  view()
  await userEvent.click(screen.getByRole('button', { name: '更多历史操作' }))
  await userEvent.click(screen.getByRole('button', { name: '更多操作' }))
  await userEvent.click(document.body)
  expect(screen.queryByRole('toolbar')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '更多历史操作' }))
  expect(screen.queryByRole('button', { name: '删除历史' })).not.toBeInTheDocument()
})

test('opening focuses a common action and arrow keys navigate the capsule', async () => {
  view()
  await userEvent.click(screen.getByRole('button', { name: '更多历史操作' }))
  expect(screen.getByRole('button', { name: '重新查询' })).toHaveFocus()
  await userEvent.keyboard('{ArrowRight}')
  expect(screen.getByRole('button', { name: '创建分享' })).toHaveFocus()
  await userEvent.keyboard('{End}')
  expect(screen.getByRole('button', { name: '收起历史操作' })).toHaveFocus()
})
