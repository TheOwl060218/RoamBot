import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useState } from 'react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, expect, test, vi } from 'vitest'

import { apiClient } from '../src/api/client'
import { AuthContext } from '../src/features/auth/authContext'
import { PlansPage, PlanDetailPage, JoinPlanPage } from '../src/features/plans/PlanPages'
import { CreatePlanControl } from '../src/features/plans/CreatePlanControl'

const snapshot = {
  destination: { name: '苏州博物馆', address: '苏州', city: '苏州', scenery_tags: ['museum'], rating: null },
  score: { total: 90, fairness: 100 },
  group_accessibility: { average_distance_km: 2, max_distance_km: 3, fairness_score: 100 },
  weather: [], daily_suitability: [], explanation: '适合出行', overall_advice: 'suitable',
}
const plan = {
  id: 'p1', name: '苏州 10.10 出行计划', city: '苏州', start_date: '2026-10-10', end_date: '2026-10-10',
  expected_count: 2, status: 'voting', ended: false, final_candidate_id: null,
  candidates: [{ id: 'a', snapshot, latest_weather: null }, { id: 'b', snapshot: { ...snapshot, destination: { ...snapshot.destination, name: '金鸡湖' } }, latest_weather: null }],
  participants: [{ id: 'owner', nickname: 'owner', role: 'owner', voted: false }],
  summary: { voted_count: 0, joined_count: 1, complete: false, candidates: [{ id: 'a', preferred_count: 0, acceptable_count: 0, all_accept: false }, { id: 'b', preferred_count: 0, acceptable_count: 0, all_accept: false }] },
  me: { id: 'owner', nickname: 'owner', preferred_id: null, acceptable_ids: [] },
  next_weather_check_at: null, invite_active: false,
}

const detailedCandidates = plan.candidates.map(candidate => ({ ...candidate, snapshot: { ...candidate.snapshot,
  weather: [{ date: plan.start_date, condition: '多云', temp_min_c: 20, temp_max_c: 26,
    precipitation_mm: 0, wind_speed_kmh: 10, humidity_percent: 60, visibility_km: 10, uv_index: 3 }],
  daily_suitability: [{ date: plan.start_date, score: 85, status: 'suitable', summary: '当天总体适合出行。', reasons: [] }],
} }))

function wrap(children: React.ReactNode, path = '/') {
  return render(<AuthContext.Provider value={{ user: { username: 'owner' }, initializing: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
  </AuthContext.Provider>)
}

afterEach(() => vi.restoreAllMocks())

test('dirty results cannot open a new plan', async () => {
  const post = vi.spyOn(apiClient, 'post')
  const props = { historyId: 'h1', trusted: true, selectedIds: ['a', 'b'], city: '苏州', startDate: '2026-10-11', endDate: '2026-10-11', originCount: 1, onRerun: vi.fn() }
  const view = wrap(<CreatePlanControl {...props} dirty />)
  expect(screen.getByRole('button', { name: '发起同行计划' })).toBeDisabled()
  expect(post).not.toHaveBeenCalled()
  view.unmount()
})

test('plan creation closes only when press and release are both outside its card', async () => {
  wrap(<CreatePlanControl historyId='h1' trusted selectedIds={['a', 'b']} city='苏州' startDate='2026-10-11' endDate='2026-10-11' originCount={1} onRerun={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '发起同行计划' }))
  const dialog = screen.getByRole('dialog')
  fireEvent.pointerDown(dialog, { clientX: -1, clientY: -1 })
  fireEvent.pointerUp(dialog, { clientX: -1, clientY: -1 })
  expect(screen.queryByRole('button', { name: '确认创建' })).toBeNull()
})

test('a dialog opened on a clean result cannot submit after conditions change', async () => {
  const post = vi.spyOn(apiClient, 'post')
  function Example() {
    const [dirty, setDirty] = useState(false)
    return <><button onClick={() => setDirty(true)}>模拟条件修改</button><CreatePlanControl historyId='h1' trusted selectedIds={['a', 'b']} city='苏州' startDate='2026-10-11' endDate='2026-10-11' originCount={1} onRerun={vi.fn()} dirty={dirty} /></>
  }
  wrap(<Example />)
  await userEvent.click(screen.getByRole('button', { name: '发起同行计划' }))
  await userEvent.click(screen.getByRole('button', { name: '模拟条件修改' }))
  expect(screen.getByRole('button', { name: '确认创建' })).toBeDisabled()
  fireEvent.submit(screen.getByRole('dialog').querySelector('form')!)
  expect(post).not.toHaveBeenCalled()
})

test('header uses the same expected total as results and separately explains joined members', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan: { ...plan, expected_count: 5, summary: { ...plan.summary, voted_count: 2, joined_count: 3 } } })
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  const header = (await screen.findByRole('heading', { name: plan.name })).closest('header')!
  expect(within(header).getByText('2/5 人已投票')).toBeVisible()
  expect(within(header).getByText('已加入 3 人，其中 1 人尚未投票。')).toBeVisible()
  expect(within(header).getByText('2 个候选')).toBeVisible()
})

test('invite header does not invent vote counts when progress is private', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan: { ...plan, participants: null, summary: null, me: { ...plan.me, id: 'guest' } } })
  wrap(<Routes><Route path='/join/:token' element={<JoinPlanPage />} /></Routes>, '/join/fixture')
  const header = (await screen.findByRole('heading', { name: plan.name })).closest('header')!
  expect(within(header).getByText('先投票，再查看进展')).toBeVisible()
  expect(within(header).queryByText(/\d+\/\d+ 人已投票/)).not.toBeInTheDocument()
})

test.each([
  ['closed', false, '等待你确定目的地'],
  ['decided', false, '苏州博物馆'],
  ['decided', true, '出行已结束'],
])('header shows next step for %s ended=%s', async (status, ended, message) => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan: { ...plan, status, ended, final_candidate_id: 'a' } })
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  const header = (await screen.findByRole('heading', { name: plan.name })).closest('header')!
  expect(within(header).getByText(message)).toBeVisible()
})
// jsdom lacks native dialog methods; browser E2E verifies modal focus and behavior.
beforeAll(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true,
    value: function(this: HTMLDialogElement) { this.setAttribute('open', '') } })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true,
    value: function(this: HTMLDialogElement) { this.removeAttribute('open') } })
})
afterAll(() => {
  Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal')
  Reflect.deleteProperty(HTMLDialogElement.prototype, 'close')
})

test('plan management stays closed until requested and expands editing on request', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan })
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  await screen.findByRole('heading', { name: plan.name })
  const titleHeader = screen.getByRole('heading', { name: plan.name }).closest('header')!
  expect(within(titleHeader).queryByRole('button', { name: '管理计划' })).not.toBeInTheDocument()
  expect(screen.getAllByRole('heading', { name: '比较候选地点' })).toHaveLength(1)
  expect(screen.queryByLabelText('计划名称')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '生成邀请', exact: true })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '管理计划' }))
  await userEvent.click(screen.getByRole('button', { name: '编辑计划信息' }))
  expect(screen.getByLabelText('计划名称')).toHaveValue(plan.name)
  expect(screen.getByLabelText('预计同行人数')).toHaveValue(2)
})

test('candidate weather is visible for one shared day and details expand on request', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan: { ...plan, candidates: detailedCandidates } })
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  await screen.findByRole('heading', { name: plan.name })
  expect(screen.getAllByText(/创建时天气/)).toHaveLength(2)
  expect(screen.getByRole('button', { name: '确定苏州博物馆' })).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '查看苏州博物馆详情' }))
  expect(screen.getByRole('button', { name: '收起苏州博物馆详情' })).toHaveAttribute('aria-expanded', 'true')
  expect(screen.queryAllByText('适合出行')).toHaveLength(0)
  await userEvent.click(screen.getByRole('button', { name: '收起苏州博物馆详情' }))
  expect(screen.getByRole('button', { name: '查看苏州博物馆详情' })).toHaveAttribute('aria-expanded', 'false')
})

test('decided destination comes first without automatically expanding all weather', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan: { ...plan, candidates: detailedCandidates, status: 'decided', final_candidate_id: 'b' } })
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  await screen.findByRole('heading', { name: plan.name })
  const cards = screen.getAllByRole('article').filter(card => card.classList.contains('plan-comparison-card'))
  expect(within(cards[0]).getByRole('heading', { name: '金鸡湖' })).toBeInTheDocument()
  expect(within(cards[0]).getByRole('button', { name: '查看金鸡湖详情' })).toHaveAttribute('aria-expanded', 'false')
  expect(within(cards[1]).getByRole('button', { name: '查看苏州博物馆详情' })).toHaveAttribute('aria-expanded', 'false')
})

test('plan center separates ended plans and links to owner detail', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plans: [plan, { ...plan, id: 'old', name: '旧计划', ended: true }] })
  wrap(<PlansPage />)
  expect(await screen.findByRole('link', { name: /苏州 10.10/ })).toHaveAttribute('href', '/plans/p1')
  expect(screen.getByRole('heading', { name: '已结束的出行' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /旧计划/ })).toBeInTheDocument()
})

test('empty active plans display a plain centered message without placeholder cards', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plans: [] })
  wrap(<PlansPage />)
  const section = await screen.findByRole('region', { name: '进行中的计划' })
  expect(within(section).getByText('还没有进行中的计划')).toBeInTheDocument()
  expect(within(section).queryByRole('link')).not.toBeInTheDocument()
  expect(within(section).queryByRole('button')).not.toBeInTheDocument()
})

test('more than three plans remain accessible in a locally scrollable rail', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plans: Array.from({ length: 5 }, (_, index) => ({
    ...plan, id: `plan-${index}`, name: `计划 ${index + 1}`,
  })) })
  wrap(<PlansPage />)
  const section = await screen.findByRole('region', { name: '进行中的计划' })
  await waitFor(() => expect(within(section).getAllByRole('link')).toHaveLength(5))
  const rail = within(section).getByRole('group', { name: '出行计划卡片' })
  const scroll = vi.fn()
  Object.defineProperty(rail, 'scrollBy', { configurable: true, value: scroll })
  await userEvent.click(within(section).getByRole('button', { name: '向右查看计划' }))
  expect(scroll).toHaveBeenCalledWith(expect.objectContaining({ left: expect.any(Number) }))
  expect(scroll.mock.calls[0][0].left).toBeGreaterThan(0)
})

test('two active plans do not acquire placeholder cards or desktop scroll controls', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plans: [plan, { ...plan, id: 'p2', name: '另一个计划' }] })
  wrap(<PlansPage />)
  const section = await screen.findByRole('region', { name: '进行中的计划' })
  await waitFor(() => expect(within(section).getAllByRole('link')).toHaveLength(2))
  expect(within(section).queryByRole('button', { name: '向右查看计划' })).not.toBeInTheDocument()
})

test('owner can choose a destination and explicitly confirm decision', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan })
  const put = vi.spyOn(apiClient, 'put').mockResolvedValue({ plan: { ...plan, status: 'decided', final_candidate_id: 'a' } })
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  await screen.findByRole('heading', { name: plan.name })
  await userEvent.click(screen.getByRole('button', { name: '确定苏州博物馆' }))
  expect(put).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '确认决定' }))
  await waitFor(() => expect(put).toHaveBeenCalledWith('/plans/p1/decision', { candidate_id: 'a' }))
  expect(await screen.findByText('已决定')).toBeInTheDocument()
})

test('owner closes voting only after confirmation and can still decide or reopen', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan })
  const put = vi.spyOn(apiClient, 'put').mockResolvedValue({ plan: { ...plan, status: 'closed' } })
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  await userEvent.click(await screen.findByRole('button', { name: '结束投票' }))
  expect(put).not.toHaveBeenCalled()
  expect(screen.getByText(/已有投票会保留/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '确认结束投票' }))
  await waitFor(() => expect(put).toHaveBeenCalledWith('/plans/p1/voting-close'))
  expect(await screen.findByText('待决定')).toBeInTheDocument()
  expect(screen.queryByRole('radio')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '确定苏州博物馆' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '重新开放投票' })).toBeInTheDocument()
})

test('failed close keeps voting controls and reports failure', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan })
  vi.spyOn(apiClient, 'put').mockRejectedValue(new Error('offline'))
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  await userEvent.click(await screen.findByRole('button', { name: '结束投票' }))
  await userEvent.click(screen.getByRole('button', { name: '确认结束投票' }))
  await screen.findByRole('alert')
  expect(screen.getByText('投票中')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '去投票' }))
  expect(screen.getByRole('radio', { name: /首选 苏州博物馆/ })).toBeInTheDocument()
})

test('closed invite exposes summary but no joining or voting controls', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan: { ...plan, status: 'closed', me: null, participants: null } })
  wrap(<Routes><Route path='/join/:inviteToken' element={<JoinPlanPage />} /></Routes>, '/join/fixture')
  expect(await screen.findByText('待决定')).toBeInTheDocument()
  expect(screen.getByText(/等待发起者决定目的地/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '当前投票结果' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '加入计划' })).not.toBeInTheDocument()
  expect(screen.queryByRole('radio')).not.toBeInTheDocument()
})

test('center prioritizes closed plans and offers deciding a destination', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plans: [plan,
    { ...plan, id: 'decided', name: '已决定计划', status: 'decided' },
    { ...plan, id: 'closed', name: '待决定计划', status: 'closed' }] })
  wrap(<PlansPage />)
  const region = await screen.findByRole('region', { name: '进行中的计划' })
  await waitFor(() => expect(within(region).getAllByRole('link')).toHaveLength(3))
  const links = within(region).getAllByRole('link')
  expect(links[0]).toHaveAttribute('href', '/plans/closed')
  expect(within(links[0]).getByText('决定目的地')).toBeInTheDocument()
  expect(links[1]).toHaveAttribute('href', '/plans/p1')
  expect(links[2]).toHaveAttribute('href', '/plans/decided')
})

test('anonymous participant joins before voting and cannot see hidden summary', async () => {
  const guestPlan = { ...plan, participants: null, summary: null, me: null }
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan: guestPlan, anonymous_csrf: null })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ plan: { ...guestPlan, me: { id: 'g', nickname: '小明', preferred_id: null, acceptable_ids: [] } }, anonymous_csrf: 'fixture' })
  wrap(<Routes><Route path='/join/:inviteToken' element={<JoinPlanPage />} /></Routes>, '/join/fixture')
  await screen.findByRole('heading', { name: plan.name })
  expect(screen.queryByText('当前投票结果')).not.toBeInTheDocument()
  await userEvent.type(screen.getByLabelText('临时昵称'), '小明')
  await userEvent.click(screen.getByRole('button', { name: '加入计划' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/public/plans/fixture/join', { nickname: '小明' }))
  await userEvent.click(await screen.findByRole('button', { name: '去投票' }))
  expect(await screen.findByRole('radio', { name: /首选 苏州博物馆/ })).toBeInTheDocument()
})

test('floating voting keeps an unsubmitted choice when dismissed and submits explicitly', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan })
  const put = vi.spyOn(apiClient, 'put').mockResolvedValue({ plan: { ...plan, me: { ...plan.me, preferred_id: 'b' } } })
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  const launch = await screen.findByRole('button', { name: '去投票' })
  expect(screen.queryByRole('radio')).not.toBeInTheDocument()
  await userEvent.click(launch)
  const panel = screen.getByRole('dialog', { name: '我的投票' })
  await userEvent.click(within(panel).getByRole('radio', { name: '首选 金鸡湖' }))
  await userEvent.keyboard('{Escape}')
  expect(put).not.toHaveBeenCalled()
  expect(launch).toHaveFocus()
  await userEvent.click(screen.getByRole('button', { name: '继续投票' }))
  expect(screen.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
  await userEvent.click(screen.getByRole('button', { name: '提交投票' }))
  await waitFor(() => expect(put).toHaveBeenCalledWith('/plans/p1/vote', { preferred_id: 'b', acceptable_ids: [] }))
  expect(await screen.findByRole('button', { name: '修改投票' })).toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: '我的投票' })).not.toBeInTheDocument()
})

test('vote failures keep the floating draft open for retry', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan })
  vi.spyOn(apiClient, 'put').mockRejectedValue(new Error('offline'))
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  await userEvent.click(await screen.findByRole('button', { name: '去投票' }))
  await userEvent.click(screen.getByRole('radio', { name: '首选 金鸡湖' }))
  await userEvent.click(screen.getByRole('button', { name: '提交投票' }))
  await screen.findByRole('alert')
  expect(screen.getByRole('dialog', { name: '我的投票' })).toBeInTheDocument()
  expect(screen.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
})

test('opening management closes voting without discarding the draft or duplicating entries', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ plan })
  const put = vi.spyOn(apiClient, 'put')
  wrap(<Routes><Route path='/plans/:planId' element={<PlanDetailPage />} /></Routes>, '/plans/p1')
  await userEvent.click(await screen.findByRole('button', { name: '去投票' }))
  await userEvent.click(screen.getByRole('radio', { name: '首选 金鸡湖' }))
  await userEvent.click(screen.getByRole('button', { name: '管理计划' }))
  expect(screen.queryByRole('dialog', { name: '我的投票' })).not.toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: '继续投票' })).toHaveLength(1)
  await userEvent.click(screen.getByRole('button', { name: '编辑计划信息' }))
  expect(screen.getByLabelText('计划名称')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '继续投票' }))
  expect(screen.getByRole('radio', { name: '首选 金鸡湖' })).toBeChecked()
  expect(put).not.toHaveBeenCalled()
})

test('guest results require explicit rerun even after login before creating', async () => {
  const rerun = vi.fn()
  wrap(<CreatePlanControl historyId={null} trusted={false} selectedIds={['a', 'b']} city='苏州'
    startDate='2026-10-10' endDate='2026-10-10' originCount={2} onRerun={rerun} />)
  await userEvent.click(screen.getByRole('button', { name: '发起同行计划' }))
  expect(rerun).not.toHaveBeenCalled()
  expect(screen.getByText('请更新推荐后创建计划。')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '更新推荐并继续' }))
  expect(rerun).toHaveBeenCalledTimes(1)
})

test('switching to an unavailable invite never retains the previous plan content', async () => {
  vi.spyOn(apiClient, 'get').mockImplementation(async (path) => {
    if (path === '/public/plans/first') return { plan, anonymous_csrf: null }
    throw new Error('unavailable')
  })
  wrap(<><Link to='/join/unavailable'>切换邀请</Link><Routes>
    <Route path='/join/:inviteToken' element={<JoinPlanPage />} />
  </Routes></>, '/join/first')
  await screen.findByRole('heading', { name: plan.name })
  await userEvent.click(screen.getByRole('link', { name: '切换邀请' }))
  await screen.findByRole('alert')
  expect(screen.queryByRole('heading', { name: plan.name })).not.toBeInTheDocument()
  expect(screen.queryByRole('radio')).not.toBeInTheDocument()
})
