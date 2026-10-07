import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { PlanVotePanel } from '../src/features/plans/PlanVotePanel'
import { workbenchPlan } from './fixtures/workbenchPlan'

test('retains an unsaved draft across close and same-plan refresh without making a request', async () => {
  const plan = workbenchPlan(), vote = vi.fn().mockResolvedValue(true), close = vi.fn()
  const view = render(<PlanVotePanel plan={plan} open busy={false} error='' onClose={close} onVote={vote} />)
  await userEvent.click(screen.getByRole('radio', { name: '首选 金鸡湖' }))
  await userEvent.click(screen.getByRole('checkbox', { name: '可接受 穹窿山' }))
  view.rerender(<PlanVotePanel plan={{ ...plan }} open={false} busy={false} error='' onClose={close} onVote={vote} />)
  expect(screen.queryByRole('radio')).not.toBeInTheDocument()
  view.rerender(<PlanVotePanel plan={{ ...plan }} open busy={false} error='' onClose={close} onVote={vote} />)
  expect(screen.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
  expect(screen.getByRole('checkbox', { name: '可接受 穹窿山' })).toBeChecked()
  expect(vote).not.toHaveBeenCalled()
})

test('preserves failed draft and closes only after success with exact payload', async () => {
  const vote = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true), close = vi.fn()
  render(<PlanVotePanel plan={workbenchPlan()} open busy={false} error='' onClose={close} onVote={vote} />)
  await userEvent.click(screen.getByRole('radio', { name: '首选 金鸡湖' }))
  await userEvent.click(screen.getByRole('checkbox', { name: '可接受 穹窿山' }))
  await userEvent.click(screen.getByRole('button', { name: '提交投票' }))
  expect(close).not.toHaveBeenCalled()
  expect(screen.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
  await userEvent.click(screen.getByRole('button', { name: '提交投票' }))
  expect(vote).toHaveBeenLastCalledWith({ preferred_id: '1', acceptable_ids: ['2'] })
  expect(close).toHaveBeenCalledOnce()
})

test('blocks editing for unauthorized or finished states and disables busy controls', () => {
  const plan = workbenchPlan(), props = { open: true, busy: false, error: '', onClose: vi.fn(), onVote: vi.fn() }
  const view = render(<PlanVotePanel plan={plan} {...props} busy />)
  expect(screen.getByRole('radio', { name: '首选 金鸡湖' })).toBeDisabled()
  for (const invalid of [{ ...plan, me: null }, { ...plan, ended: true }, { ...plan, status: 'closed' as const }, { ...plan, status: 'decided' as const }]) {
    view.rerender(<PlanVotePanel plan={invalid} {...props} />)
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
  }
})

test('rejects a removed candidate and resets draft for another plan', async () => {
  const plan = workbenchPlan(), props = { open: true, busy: false, error: '', onClose: vi.fn(), onVote: vi.fn() }
  const view = render(<PlanVotePanel plan={plan} {...props} />)
  await userEvent.click(screen.getByRole('radio', { name: '首选 金鸡湖' }))
  view.rerender(<PlanVotePanel plan={{ ...plan, candidates: [plan.candidates[0]] }} {...props} />)
  expect(screen.getByRole('button', { name: '提交投票' })).toBeDisabled()
  view.rerender(<PlanVotePanel plan={{ ...plan, id: 'other' }} {...props} />)
  expect(screen.getByRole('radio', { name: '首选 金鸡湖' })).not.toBeChecked()
})

test('prevents duplicate saves while the first submission is pending', async () => {
  let finish!: (saved: boolean) => void
  const vote = vi.fn(() => new Promise<boolean>(resolve => { finish = resolve })), close = vi.fn()
  render(<PlanVotePanel plan={workbenchPlan()} open busy={false} error='' onClose={close} onVote={vote} />)
  await userEvent.click(screen.getByRole('radio', { name: '首选 金鸡湖' }))
  const button = screen.getByRole('button', { name: '提交投票' })
  await userEvent.dblClick(button)
  expect(vote).toHaveBeenCalledOnce()
  expect(screen.getByRole('radio', { name: '首选 金鸡湖' })).toBeDisabled()
  expect(button).toBeDisabled()
  await act(async () => finish(false))
  await waitFor(() => expect(button).toBeEnabled())
  expect(close).not.toHaveBeenCalled()
  expect(screen.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
})
