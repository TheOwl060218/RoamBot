import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/client'
import { HistoryActionsMenu } from '../src/features/history/HistoryActionsMenu'

afterEach(() => vi.restoreAllMocks())
it('keeps copy visible immediately after creating a history share', async () => {
  const user = userEvent.setup()
  const copy = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue()
  vi.spyOn(apiClient, 'post').mockResolvedValue({ share: {
    id: 'share', history_id: 'history', url: '/share/share', created_at: '2026-10-14',
  } })
  render(<HistoryActionsMenu historyId='history' rerunning={false} rerunDisabled={false}
    onRerun={vi.fn()} onDelete={vi.fn()} onStatus={vi.fn()} />)
  await user.click(screen.getByRole('button', { name: '更多历史操作' }))
  await user.click(screen.getByRole('button', { name: '创建分享' }))
  await user.click(await screen.findByRole('button', { name: '复制分享链接' }))
  expect(copy).toHaveBeenCalledWith(new URL('/share/share', window.location.origin).href)
  expect(screen.queryByRole('button', { name: '复制分享链接' })).not.toBeInTheDocument()
})
