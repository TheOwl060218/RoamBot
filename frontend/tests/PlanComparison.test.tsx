import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { PlanComparison } from '../src/features/plans/PlanComparison'
import { workbenchPlan } from './fixtures/workbenchPlan'

test('opens one named explanation outside the card and toggles it from the same button', async () => {
  render(<PlanComparison plan={workbenchPlan()} />)
  const first = screen.getByRole('button', { name: '查看苏州博物馆详情' })
  await userEvent.click(first)
  const popup = screen.getByRole('dialog', { name: '苏州博物馆 · 12.30 出行说明' })
  expect(popup.closest('.plan-comparison-card')).toBeNull()
  expect(within(popup).getByText('当日出行说明')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '查看金鸡湖详情' }))
  expect(screen.getAllByRole('dialog')).toHaveLength(1)
  expect(screen.getByRole('dialog')).toHaveAccessibleName('金鸡湖 · 12.30 出行说明')
  await userEvent.click(screen.getByRole('button', { name: '收起金鸡湖详情' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('dismisses explanation on Escape or outside click and never restores it after changing dates', async () => {
  render(<PlanComparison plan={workbenchPlan()} />)
  const trigger = screen.getByRole('button', { name: '查看苏州博物馆详情' })
  await userEvent.click(trigger)
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
  expect(trigger).toHaveFocus()
  await userEvent.click(trigger)
  await userEvent.click(screen.getByRole('heading', { name: '比较候选地点' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  await userEvent.click(trigger)
  await userEvent.click(screen.getByRole('button', { name: '12.31' }))
  await userEvent.click(screen.getByRole('button', { name: '12.30' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveAttribute('aria-expanded', 'false')
})

test('announces an offscreen all-dates table on expansion but clears the notice on collapse', async () => {
  const bounds = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ top: 2000, bottom: 2100, left: 0, right: 300, width: 300, height: 100 } as DOMRect)
  try {
    render(<PlanComparison plan={workbenchPlan()} />)
    await userEvent.click(screen.getByRole('button', { name: '查看全部日期' }))
    expect(await screen.findByRole('status')).toHaveTextContent('候选卡片下方')
    await userEvent.click(screen.getByRole('button', { name: '收起全部日期' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  } finally { bounds.mockRestore() }
})

test('synchronizes a cross-year selected day for every candidate without expanding all dates', async () => {
  render(<PlanComparison plan={workbenchPlan()} />)
  expect(screen.getAllByRole('article')).toHaveLength(6) // three cards with one nested weather article each
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '12.31' }))
  for (const heading of screen.getAllByRole('heading', { level: 3 })) {
    const card = heading.closest('.plan-comparison-card')!
    expect(within(card as HTMLElement).getByText('12月31日')).toBeVisible()
    expect(within(card as HTMLElement).getByText('小雨')).toBeVisible()
    expect(within(card as HTMLElement).queryByText('12月30日')).not.toBeInTheDocument()
  }
  expect(screen.queryByText('禁止展示的 AI 推荐理由')).not.toBeInTheDocument()
})

test('does not substitute another day when a candidate lacks selected weather', async () => {
  const plan = workbenchPlan()
  plan.candidates[0].snapshot.weather = plan.candidates[0].snapshot.weather.slice(0, 1)
  render(<PlanComparison plan={plan} />)
  await userEvent.click(screen.getByRole('button', { name: '12.31' }))
  expect(screen.getByText('该日暂无天气记录')).toBeVisible()
  expect(screen.getAllByText('小雨')).toHaveLength(2)
})

test('preserves selected day on refresh, resets on a new plan, and shows unified date details', async () => {
  const plan = workbenchPlan()
  const view = render(<PlanComparison plan={plan} />)
  await userEvent.click(screen.getByRole('button', { name: '1.1' }))
  view.rerender(<PlanComparison plan={{ ...plan, updated_at: 'later' }} />)
  expect(screen.getByRole('button', { name: '1.1' })).toHaveAttribute('aria-pressed', 'true')
  await userEvent.click(screen.getByRole('button', { name: '查看全部日期' }))
  const table = screen.getByRole('table', { name: '全部日期天气对比' })
  expect(within(table).getAllByRole('columnheader')).toHaveLength(4)
  expect(within(table).getAllByRole('row')).toHaveLength(4)
  view.rerender(<PlanComparison plan={{ ...plan, id: 'other' }} />)
  expect(screen.getByRole('button', { name: '12.30' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

test('never borrows old suitability for newly checked weather, including a failed check with retained data', () => {
  const plan = workbenchPlan()
  plan.candidates[0].latest_weather = { checked_at: '2026-10-06T00:00:00Z', status: 'failed', source: 'demo', change: 'unavailable', risk: null, weather: plan.candidates[0].snapshot.weather, last_success_at: '2026-10-05T00:00:00Z' }
  render(<PlanComparison plan={plan} />)
  const card = screen.getByRole('heading', { name: '苏州博物馆' }).closest('.plan-comparison-card') as HTMLElement
  expect(within(card).getByText('暂无判断')).toBeVisible()
  expect(within(card).getByText(/检查失败/)).toBeVisible()
  expect(within(card).queryByText('当日出行说明')).not.toBeInTheDocument()
  expect(within(card).queryByRole('button', { name: '查看苏州博物馆详情' })).not.toBeInTheDocument()
})

test('shows fresh daily advice and expands its explanation instead of the snapshot text', async () => {
  const plan = workbenchPlan()
  plan.candidates[0].latest_weather = {
    checked_at: '2026-10-07T00:00:00Z', status: 'success', source: 'demo', change: 'worsened', risk: 'high',
    weather: plan.candidates[0].snapshot.weather,
    daily_suitability: [{ date: plan.start_date, score: 35, status: 'not_recommended', summary: '最新天气有强降水，建议调整日期。', reasons: [] }],
    last_success_at: '2026-10-07T00:00:00Z',
  } as NonNullable<typeof plan.candidates[0]['latest_weather']>
  render(<PlanComparison plan={plan} />)
  const card = screen.getByRole('heading', { name: '苏州博物馆' }).closest('.plan-comparison-card') as HTMLElement
  expect(within(card).getByText('不建议当日前往')).toBeVisible()
  await userEvent.click(within(card).getByRole('button', { name: '查看苏州博物馆详情' }))
  const popup = screen.getByRole('dialog', { name: '苏州博物馆 · 12.30 出行说明' })
  expect(within(popup).getByText('最新天气有强降水，建议调整日期。')).toBeVisible()
  expect(within(popup).queryByText('当日出行说明')).not.toBeInTheDocument()
})
