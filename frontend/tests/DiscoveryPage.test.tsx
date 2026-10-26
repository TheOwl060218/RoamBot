import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient, ApiError } from '../src/api/client'
import { DiscoveryPage } from '../src/pages/DiscoveryPage'
import type { DiscoveryCard, DiscoverySnapshot } from '../src/features/discovery/types'
import { CommandRoot } from '../src/features/commands/CommandRoot'

vi.mock('../src/features/auth/authContext', async importOriginal => ({
  ...await importOriginal<typeof import('../src/features/auth/authContext')>(),
  useAuth: () => ({ initializing: false }),
}))
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })
const card = (id: string, name: string): DiscoveryCard => ({
  place: { id, name, city: '苏州', address: '实际地址', coordinate: { longitude: 120, latitude: 31, system: 'gcj02' },
    map_type: '书店', map_url: 'https://www.amap.com/detail/1', facts: {} },
  experience: '翻书休息', reason: `${name}的资料介绍了实际空间，可以结合你这次想放松的需求比较选择。`,
  sources: [{ id: 'e1', kind: 'search_excerpt', title: '场地介绍', url: 'https://example.org/venue' }], route: null, weather: null,
})
const snapshot = (cards: DiscoveryCard[], status: DiscoverySnapshot['status']): DiscoverySnapshot => ({
  id: 'new-job', status, stage: status === 'running' ? '正在核对地点资料' : '', cards,
  reply: status === 'completed' ? '已找到不同的去处。' : '', request_location: false, center_name: null,
  context: { origin: null, region: '苏州', max_distance_km: null, start_date: null, end_date: null }, source: 'demo',
})
function mount() { return render(<MemoryRouter><DiscoveryPage /></MemoryRouter>) }
function mountCommands() {
  return render(<MemoryRouter initialEntries={['/explore']}><Routes><Route element={<CommandRoot />}>
    <Route path='/explore' element={<DiscoveryPage />} />
  </Route></Routes></MemoryRouter>)
}
async function send(text: string) {
  const user = userEvent.setup()
  await user.type(screen.getByRole('textbox', { name: '继续补充条件' }), text)
  await user.keyboard('{Enter}')
}

describe('open-ended discovery', () => {
  it('uses the condensed intent title and preserves the complete request in the conversation', () => {
    const request = '想在苏州寻找适合周末散步和摄影的公园，希望分布在不同片区，避开之前已经推荐过的地点'
    const result = { ...snapshot([card('p1', '河边公园')], 'completed'), display_title: '苏州不同片区的公园摄影' }
    render(<MemoryRouter><DiscoveryPage initialSnapshot={result} initialMessage={request} /></MemoryRouter>)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('苏州不同片区的公园摄影')
    expect(within(screen.getByRole('log', { name: '本次对话记录' })).getByText(request)).toBeInTheDocument()
  })
  it('keeps legacy request wording with compact styling when no condensed title exists', () => {
    const request = '想在苏州寻找适合周末散步和摄影的公园，希望分布在不同片区，避开之前已经推荐过的地点'
    render(<MemoryRouter><DiscoveryPage initialSnapshot={snapshot([card('p1', '河边公园')], 'completed')} initialMessage={request} /></MemoryRouter>)
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent(request)
    expect(heading).toHaveAttribute('data-long-request', 'true')
    expect(heading).not.toHaveTextContent('苏州的去处')
  })
  it('opens all current places on the map, shows the selected card and returns to that rail card without a new search', async () => {
    const cards = [card('p1', '湖边书店'), card('p2', '河边公园')]
    const post = vi.spyOn(apiClient, 'post')
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ enabled: false }) })
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<MemoryRouter><DiscoveryPage initialSnapshot={snapshot(cards, 'completed')} /></MemoryRouter>)
    const rail = screen.getByRole('region', { name: '推荐去处' })
    const controls = screen.getByRole('button', { name: '地图', exact: true }).closest('.discovery-results-toolbar')
    expect(controls).not.toBeNull()
    expect(controls?.closest('.discovery-browse')).toBeNull()
    const original = Array.from(rail.querySelectorAll('[data-place-id]'))
    await user.click(screen.getByRole('button', { name: '地图', exact: true }))
    const map = await screen.findByRole('dialog', { name: '推荐地图' })
    expect(within(map).getByText('2 个推荐地点')).toBeVisible()
    await user.click(within(map).getByRole('button', { name: '2 · 河边公园' }))
    const preview = within(map).getByRole('article', { name: '河边公园推荐卡片' })
    expect(within(preview).getByRole('button', { name: '收藏河边公园' })).toBeVisible()
    expect(within(preview).getByRole('button', { name: '加入行程' })).toBeVisible()
    expect(within(preview).getByText('实际地址')).toBeVisible()
    await user.click(within(preview).getByRole('button', { name: '展开卡片' }))
    expect(within(preview).getByText('实际地址')).toBeVisible()
    await user.click(within(map).getByRole('button', { name: '关闭地图' }))
    await waitFor(() => expect(original[1]).toHaveAttribute('data-map-focused', 'true'))
    expect(screen.getByRole('button', { name: '了解河边公园' })).toHaveFocus()
    expect(Array.from(rail.querySelectorAll('[data-place-id]'))).toEqual(original)
    expect(post).not.toHaveBeenCalled()
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('changes batch directly, keeps bound selections, and explains both buttons on hover', async () => {
    const old = { ...snapshot([card('p1', '已选地点'), card('p2', '之前的地点')], 'completed'), id: 'owned' }
    const changed = { ...snapshot([card('p1', '已选地点'), card('p3', '新的地点')], 'completed'),
      intent: 'search', exploration: { mode: 'batch', remaining: 0, seen_count: 3, new_count: 1, used_reserve: true } }
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ id: 'new-job' })
    vi.spyOn(apiClient, 'get').mockResolvedValue(changed)
    render(<MemoryRouter><DiscoveryPage initialSnapshot={old} initialMessage='苏州看看书店' /></MemoryRouter>)
    await userEvent.click(screen.getAllByRole('button', { name: '加入比较' })[0])
    const batch = screen.getByRole('button', { name: '换一批' })
    expect(batch).toHaveAttribute('title', expect.stringContaining('还没展示'))
    expect(screen.getByRole('button', { name: '看看其他区域' })).toHaveAttribute('title', expect.stringContaining('其他区域'))
    await userEvent.click(batch)
    await screen.findByRole('heading', { name: '新的地点' })
    expect(post).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledWith('/discovery/jobs', expect.objectContaining({
      explore_mode: 'batch', previous_id: 'owned', view: expect.objectContaining({ selected_ids: ['p1'] }),
    }))
    expect(screen.getByRole('button', { name: '已选入比较' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('heading', { name: '之前的地点' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '苏州看看书店' })).toBeInTheDocument()
  })
  it('keeps results when other areas return nothing and prevents repeated clicks while pending', async () => {
    const old = { ...snapshot([card('p1', '保留的地点')], 'completed'), id: 'owned' }
    let finish!: (value: { id: string }) => void
    const post = vi.spyOn(apiClient, 'post').mockImplementation(() => new Promise(resolve => { finish = resolve }) as never)
    vi.spyOn(apiClient, 'get').mockResolvedValue({ ...snapshot([], 'completed'), intent: 'search',
      exploration: { mode: 'area', remaining: 0, seen_count: 1, new_count: 0, used_reserve: false },
      reply: '暂未找到其他区域的合适去处，当前推荐已保留。' })
    render(<MemoryRouter><DiscoveryPage initialSnapshot={old} /></MemoryRouter>)
    const area = screen.getByRole('button', { name: '看看其他区域' })
    await userEvent.dblClick(area)
    expect(post).toHaveBeenCalledTimes(1)
    expect(area).toBeDisabled()
    finish({ id: 'new-job' })
    await screen.findByText('暂未找到其他区域的合适去处，当前推荐已保留。')
    expect(screen.getByRole('heading', { name: '保留的地点' })).toBeInTheDocument()
    expect(area).toBeEnabled()
    expect(post).toHaveBeenCalledWith('/discovery/jobs', expect.objectContaining({ explore_mode: 'area' }))
  })
  it('offers the position capsule for a city-only result and keeps region-only choice on followups', async () => {
    const locate = vi.fn()
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: locate } })
    const initial = { ...snapshot([card('p1', '公园')], 'completed'), context: { origin: null, region: '苏州', max_distance_km: null } }
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ id: 'area-job' })
    vi.spyOn(apiClient, 'get').mockResolvedValue({ ...initial, id: 'area-job',
      position: { source: 'region', label: '苏州', approximate: false, accuracy_m: null, captured_at: null } })
    render(<MemoryRouter><DiscoveryPage initialSnapshot={initial} initialMessage='去苏州看公园' /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: /修改位置.*苏州/ }))
    await userEvent.click(screen.getByRole('button', { name: '只按苏州推荐' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/discovery/jobs', expect.objectContaining({
      message: '去苏州看公园', use_location: false,
    })))
    await screen.findByRole('button', { name: /推荐地区：苏州/ })
    await send('换成湖边走走')
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    expect(post.mock.calls[1][1]).toMatchObject({ message: '换成湖边走走', use_location: false })
    expect(post.mock.calls[1][1]).not.toHaveProperty('location')
    expect(locate).not.toHaveBeenCalled()
    expect([...screen.getByRole('log').querySelectorAll('.user')].map(node => node.textContent)).toEqual(['去苏州看公园', '换成湖边走走'])
  })
  it('cancels before the job creation response and deletes that late job without polling it', async () => {
    let finish!: (value: { id: string }) => void
    vi.spyOn(apiClient, 'post').mockImplementation(() => new Promise(resolve => { finish = resolve }) as never)
    const get = vi.spyOn(apiClient, 'get')
    const remove = vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mount(); await send('去附近散步')
    await userEvent.click(screen.getByRole('button', { name: '停止查找' }))
    finish({ id: 'late-cancelled-job' })
    await waitFor(() => expect(remove).toHaveBeenCalledWith('/discovery/jobs/late-cancelled-job'))
    expect(get).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: '停止查找' })).not.toBeInTheDocument()
  })
  it('preserves the first results and second input after a connection failure, then allows an explicit retry', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ id: 'new-job' })
      .mockRejectedValueOnce(new ApiError(0, 'network_unavailable', '暂时连接不上服务，请稍后重试。'))
      .mockResolvedValue({ id: 'retry-job' })
    vi.spyOn(apiClient, 'get').mockImplementation(async path => ({ ...snapshot([card('p1', '保留的地点')], 'completed'),
      id: path.split('/').at(-1) }) as never)
    mount(); await send('苏州看看书店')
    const first = await screen.findByRole('heading', { name: '保留的地点' })
    await send('换成湖边走走')
    await screen.findByRole('alert')
    const input = screen.getByRole('textbox', { name: '继续补充条件' })
    expect(input).toHaveValue('换成湖边走走')
    expect(screen.getByRole('heading', { name: '保留的地点' })).toBe(first)
    expect(post).toHaveBeenCalledTimes(2)
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(3))
    expect(post).toHaveBeenLastCalledWith('/discovery/jobs', expect.objectContaining({
      message: '换成湖边走走', previous_id: 'new-job',
    }))
    await waitFor(() => expect(input).toHaveValue(''))
  })
  it('answers a question in the current detail without replacing results or navigating to legacy search', async () => {
    let jobs=0
    const post=vi.spyOn(apiClient,'post').mockImplementation(async path=>{
      if(path==='/discovery/jobs') return {id:++jobs===1?'new-job':'question-job'} as never
      if(path.endsWith('/proposals')) return {request_id:'question-command',proposal:'signed-question',
        question:null,requires_confirmation:false,actions:[{tool:'explain_result',arguments:{}}]} as never
      return {status:'completed',steps:[{tool:'explain_result',status:'completed',result:{reply:'这处当前已查询到的步行路程是1.2公里。'}}]} as never
    })
    vi.spyOn(apiClient,'get').mockImplementation(async path=>path.endsWith('question-job')
      ? {...snapshot([],'completed'),id:'question-job',intent:'business',reply:''} as never
      : snapshot([card('p1','独立书店')],'completed') as never)
    vi.spyOn(apiClient,'remove').mockResolvedValue({})
    mountCommands();await send('苏州看看书店')
    const heading=await screen.findByRole('heading',{name:'独立书店'})
    await userEvent.click(screen.getByRole('button',{name:'了解独立书店'}))
    await screen.findByRole('dialog',{name:'独立书店详情'})
    await userEvent.click(screen.getByRole('button',{name:'打开继续聊这次出游'}))
    await userEvent.type(document.querySelector('.layer-chat-panel textarea')!,'这里怎么走{Enter}')
    await waitFor(()=>expect(document.querySelector('.layer-chat-messages')).toHaveTextContent('这处当前已查询到的步行路程是1.2公里。'))
    expect(screen.getByRole('dialog',{name:'独立书店详情'})).toBeInTheDocument()
    expect(document.querySelector('.discovery-card h2')).toBe(heading)
    expect(post).toHaveBeenCalledWith('/assistant/commands/proposals',expect.objectContaining({
      context:expect.objectContaining({discovery_job_id:'new-job',focused_id:'p1',layer:'detail'})}))
    expect(post.mock.calls.filter(([path])=>path==='/discovery/jobs')).toHaveLength(2)
    expect(post).toHaveBeenCalledWith('/discovery/jobs',expect.objectContaining({
      message:'这里怎么走',previous_id:'new-job',view:{focused_id:'p1',selected_ids:[],layer:'detail'}}))
  })
  it('shows available visiting facts and a compact address, without inventing a route duration', async () => {
    const place = card('p1', '湖边公园')
    place.place.facts = { opentime_week: '周一至周日 09:00-20:00', cost: '20' }
    place.route = { mode: 'walking', distance_km: 1.2 }
    render(<MemoryRouter><DiscoveryPage initialSnapshot={snapshot([place], 'completed')} /></MemoryRouter>)
    expect(screen.getByText('周一至周日 09:00-20:00')).toBeInTheDocument()
    expect(screen.getByText('¥20 / 人')).toBeInTheDocument()
    expect(screen.getByText('实际地址')).toHaveAttribute('title', '实际地址')
    expect(screen.queryByText(/约0分钟/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '了解湖边公园' }))
    expect(within(screen.getByRole('dialog', { name: '湖边公园详情' })).getByText('实际地址')).toBeVisible()
  })
  it('uses returned reasons and reveals source links only in the opened card, without exposing raw excerpts', async () => {
    const cards = Array.from({ length: 9 }, (_, index) => card('p' + index, '去处' + index))
    cards[0].sources = [{ id: 'proof', kind: 'search_excerpt', title: '核验原文', url: 'https://example.org/proof', excerpt: '不应展示的核验原文' }]
    render(<MemoryRouter><DiscoveryPage initialSnapshot={snapshot(cards, 'completed')} /></MemoryRouter>)
    expect(screen.getByRole('region', { name: '推荐去处' }).querySelectorAll('[data-place-id]')).toHaveLength(9)
    expect(screen.getByText(cards[0].reason)).toBeVisible()
    expect(screen.queryByRole('link', { name: '推荐依据' })).not.toBeInTheDocument()
    const user = userEvent.setup()
    await user.click(screen.getAllByRole('button', { name: '加入比较' })[0])
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '了解去处0' }))
    const detail = await screen.findByRole('dialog', { name: '去处0详情' })
    expect(within(detail).getByText(cards[0].reason)).toBeVisible()
    expect(within(detail).getByText('资料来源 · 1')).toBeVisible()
    await user.click(within(detail).getByText('资料来源 · 1'))
    expect(within(detail).getByRole('link', { name: '核验原文 ↗' })).toHaveAttribute('href', 'https://example.org/proof')
    expect(screen.queryByText('不应展示的核验原文')).not.toBeInTheDocument()
  })
  it('retains the submitted wish as title when planning fails before intent is available', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ id: 'failed-job' })
      .mockResolvedValue({ id: 'retry-job' })
    vi.spyOn(apiClient, 'get').mockImplementation(async path => ({ ...snapshot([], 'failed'),
      id: path.split('/').at(-1), intent: null, reply: '这轮查询尚未完成。' }) as never)
    vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mount(); await send('去苏州躺着放松的地方')
    await screen.findByText('这轮查询尚未完成。')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('去苏州躺着放松的地方')
    await send('再试一次')
    expect(post).toHaveBeenLastCalledWith('/discovery/jobs', expect.objectContaining({
      message: '再试一次', previous_id: 'failed-job',
    }))
  })
  it('requests device location automatically and continues the same wish without duplicate chat', async () => {
    const position = { coords: { latitude: 31.3, longitude: 120.6, accuracy: 40 }, timestamp: 1000 } as GeolocationPosition
    const locate = vi.fn((success: PositionCallback) => success(position))
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: locate } })
    let jobs = 0
    const post = vi.spyOn(apiClient, 'post').mockImplementation(async () => ({ id: `job-${++jobs}` }) as never)
    vi.spyOn(apiClient, 'get').mockImplementation(async path => path.endsWith('job-1')
      ? { ...snapshot([], 'completed'), id: 'job-1', request_location: true,
        reply: '使用当前位置查找附近的去处。', context: { origin: null, region: '苏州', max_distance_km: 5 } } as never
      : { ...snapshot([card('p1', '湖边绿地')], 'completed'), id: 'job-2' } as never)
    vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mount(); await send('苏州附近放松一下的地方')
    expect(await screen.findByRole('heading', { name: '湖边绿地' })).toBeInTheDocument()
    expect(locate).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenLastCalledWith('/discovery/jobs', expect.objectContaining({
      message: '苏州附近放松一下的地方', previous_id: 'job-1',
      location: { latitude: 31.3, longitude: 120.6, system: 'wgs84' },
      location_details: { source: 'device', accuracy_m: 40, captured_at: 1000, replace_origin: true },
    }))
    expect([...screen.getByRole('log').querySelectorAll('.user')].map(node => node.textContent)).toEqual(['苏州附近放松一下的地方'])
    expect(screen.queryByRole('button', { name: '使用当前位置' })).not.toBeInTheDocument()
  })

  it('keeps chat usable after location refusal without repeatedly prompting or starting another query', async () => {
    const locate = vi.fn((_success: PositionCallback, fail: PositionErrorCallback) =>
      fail({ code: 1 } as GeolocationPositionError))
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: locate } })
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ id: 'new-job' })
    vi.spyOn(apiClient, 'get').mockResolvedValue({ ...snapshot([], 'completed'), request_location: true })
    vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mount(); await send('附近看看')
    expect(await screen.findByRole('button', { name: /未获定位授权/ })).toBeEnabled()
    expect(locate).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('textbox', { name: '继续补充条件' })).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: /未获定位授权/ }))
    expect(screen.getByRole('button', { name: '重新定位' })).toBeEnabled()
  })

  it('ignores a late location response after a newer wish', async () => {
    let located: PositionCallback | undefined
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: vi.fn((success: PositionCallback) => { located = success }) } })
    let jobs = 0
    const post = vi.spyOn(apiClient, 'post').mockImplementation(async () => ({ id: `job-${++jobs}` }) as never)
    vi.spyOn(apiClient, 'get').mockImplementation(async path => path.endsWith('job-1')
      ? { ...snapshot([], 'completed'), id: 'job-1', request_location: true } as never
      : { ...snapshot([card('p1', '杭州书店')], 'completed'), id: 'job-2' } as never)
    vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mount(); await send('附近看看')
    await waitFor(() => expect(located).toBeDefined())
    await send('改去杭州看书店')
    await screen.findByRole('heading', { name: '杭州书店' })
    located!({ coords: { latitude: 31.3, longitude: 120.6 } } as GeolocationPosition)
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('改去杭州看书店')
  })

  it('does not loop location prompts if the resumed backend still requests location', async () => {
    const locate = vi.fn((success: PositionCallback) => success({
      coords: { latitude: 31.3, longitude: 120.6 },
    } as GeolocationPosition))
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: locate } })
    let jobs = 0
    const post = vi.spyOn(apiClient, 'post').mockImplementation(async () => ({ id: `job-${++jobs}` }) as never)
    vi.spyOn(apiClient, 'get').mockImplementation(async () => ({
      ...snapshot([], 'completed'), id: `job-${jobs}`, request_location: true,
    }) as never)
    vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mount(); await send('附近看看')
    expect(await screen.findByRole('button', { name: /重新定位或选择位置/ })).toBeEnabled()
    expect(post).toHaveBeenCalledTimes(2)
    expect(locate).toHaveBeenCalledTimes(1)
  })

  it('does not request device location when a departure point is already supplied', async () => {
    const locate = vi.fn()
    vi.stubGlobal('navigator', { geolocation: { getCurrentPosition: locate } })
    vi.spyOn(apiClient, 'post').mockResolvedValue({ id: 'new-job' })
    vi.spyOn(apiClient, 'get').mockResolvedValue({ ...snapshot([card('p1', '湖边绿地')], 'completed'),
      context: { origin: '苏州站', region: '苏州', max_distance_km: 5 } })
    vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mount(); await send('从苏州站出发附近看看')
    await screen.findByRole('heading', { name: '湖边绿地' })
    expect(locate).not.toHaveBeenCalled()
  })

  it('sends the complete original wish without inventing required scenery, origin or dates', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ id: 'new-job' })
    vi.spyOn(apiClient, 'get').mockResolvedValue(snapshot([card('p1', '独立书店')], 'completed'))
    vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mount()
    await send('我想找本摄影集，坐下来翻翻')
    expect(post).toHaveBeenCalledWith('/discovery/jobs', { message: '我想找本摄影集，坐下来翻翻', previous_id: null })
    expect(await screen.findByRole('heading', { name: '独立书店' })).toBeInTheDocument()
    expect(screen.getByText(/资料介绍了实际空间/)).toBeInTheDocument()
    expect(screen.queryByText(/匹配指数|平均.*km|暂无评分/)).not.toBeInTheDocument()
  })

  it('appends later batches without replacing or moving the first card DOM', async () => {
    vi.spyOn(apiClient, 'post').mockResolvedValue({ id: 'new-job' })
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce(snapshot([card('p1', '独立书店')], 'running'))
      .mockResolvedValue(snapshot([card('p1', '独立书店'), card('p2', '另一种体验')], 'completed'))
    vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mount(); await send('推荐些不同的去处')
    const first = await screen.findByRole('heading', { name: '独立书店' })
    await screen.findByRole('heading', { name: '另一种体验' }, { timeout: 2500 })
    expect(screen.getByRole('heading', { name: '独立书店' })).toBe(first)
    expect([...document.querySelectorAll('[data-place-id]')].map(node => node.getAttribute('data-place-id'))).toEqual(['p1', 'p2'])
  })

  it('keeps the user message available for retry after a failed start', async () => {
    vi.spyOn(apiClient, 'post').mockRejectedValue(new Error('服务暂未完成'))
    mount(); await send('附近有没有可以休息的地方')
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('服务暂未完成'))
    expect(screen.getByRole('textbox', { name: '继续补充条件' })).toHaveValue('附近有没有可以休息的地方')
  })

  it('hands business messages to the executor while retaining the actual source, card DOM and detail layer', async () => {
    let jobs = 0
    const post = vi.spyOn(apiClient, 'post').mockImplementation(async path => {
      if (path === '/discovery/jobs') return { id: ++jobs === 1 ? 'new-job' : 'action-job' } as never
      if (path.endsWith('/proposals')) return { request_id: 'business-request', proposal: 'signed',
        question: null, requires_confirmation: false, actions: [{ tool: 'favorite_place', arguments: { place: 1 } }] } as never
      return { status: 'completed', steps: [{ tool: 'favorite_place', status: 'completed', result: {} }] } as never
    })
    vi.spyOn(apiClient, 'get').mockImplementation(async path => path.endsWith('action-job')
      ? { ...snapshot([], 'completed'), id: 'action-job', intent: 'business', reply: '' } as never
      : snapshot([card('p1', '独立书店')], 'completed') as never)
    vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mountCommands(); await send('苏州看看书店')
    const heading = await screen.findByRole('heading', { name: '独立书店' })
    await userEvent.click(screen.getByRole('button', { name: '了解独立书店' }))
    expect(screen.getByRole('dialog', { name: '独立书店详情' })).toBeInTheDocument()
    // Keep the inline composer for this unit test; layered keyboard is covered in e2e.
    await send('收藏第一个')
    await waitFor(() => expect(post.mock.calls.some(([path]) => path.endsWith('/execute'))).toBe(true))
    expect(screen.getByRole('dialog', { name: '独立书店详情' })).toBeInTheDocument()
    expect(document.querySelector('[data-place-id="p1"] h2')).toBe(heading)
    const proposal = post.mock.calls.find(([path]) => path.endsWith('/proposals'))!
    expect(proposal[1]).toMatchObject({ message: '收藏第一个', context: {
      discovery_job_id: 'new-job', focused_id: 'p1', layer: 'detail',
    } })
    expect(post.mock.calls.filter(([path]) => path === '/discovery/jobs')).toHaveLength(2)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('苏州看看书店')
  })

  it.each([false, true])('opens comparison with legacy sequence or atomic task (%s), without fake scores or dates', async atomic => {
    let jobs = 0
    vi.spyOn(apiClient, 'post').mockImplementation(async path => {
      if (path === '/discovery/jobs') return { id: ++jobs === 1 ? 'new-job' : 'action-job' } as never
      if (path.endsWith('/proposals')) return { request_id: 'compare-request', proposal: 'compare-signed',
        question: null, requires_confirmation: false, actions: [] } as never
      return { status: 'completed', steps: atomic ? [
        { tool: 'compare_places', status: 'completed', result: { effect: { tool: 'show_comparison', arguments: { ids: ['p1', 'p2'] } } } },
      ] : [
        { tool: 'select_candidates', status: 'completed', result: { effect: { tool: 'select_candidates', arguments: { ids: ['p1', 'p2'] } } } },
        { tool: 'show_comparison', status: 'completed', result: { effect: { tool: 'show_comparison', arguments: {} } } },
      ] } as never
    })
    vi.spyOn(apiClient, 'get').mockImplementation(async path => path.endsWith('action-job')
      ? { ...snapshot([], 'completed'), id: 'action-job', intent: 'business', reply: '' } as never
      : snapshot([card('p1', '独立书店'), card('p2', '湖边绿地')], 'completed') as never)
    vi.spyOn(apiClient, 'remove').mockResolvedValue({})
    mountCommands(); await send('苏州不同体验'); await screen.findByRole('heading', { name: '独立书店' })
    await send('选前两个比较一下')
    expect(await screen.findByRole('dialog', { name: '地点对比' })).toBeInTheDocument()
    expect(screen.queryByText(/匹配指数|平均.*km|暂无评分/)).not.toBeInTheDocument()
  })
})

it('restores the dialogue returned with a history snapshot', () => {
  const restored = { ...snapshot([card('saved', '公园')], 'completed'), conversation: [
    { role: 'user', content: '想在苏州找一片湖边走走' },
    { role: 'user', content: '换成公园也可以，别爬山' },
  ] }
  render(<MemoryRouter><DiscoveryPage initialSnapshot={restored} initialMessage='换成公园也可以，别爬山' archiveHistoryId='saved-history' /></MemoryRouter>)
  expect(screen.getByText('想在苏州找一片湖边走走')).toBeInTheDocument()
  expect(screen.getByRole('log')).toHaveTextContent('换成公园也可以，别爬山')
  expect(screen.getByText('已找到不同的去处。')).toBeInTheDocument()
})


it('restores existing results and dialogue on remount without starting a paid query', async () => {
  const saved = { ...snapshot([card('saved', '公园')], 'completed'), intent: 'search' as const }
  vi.spyOn(apiClient, 'get').mockResolvedValue(saved)
  const post = vi.spyOn(apiClient, 'post')
  const first = render(<MemoryRouter><DiscoveryPage initialSnapshot={saved} initialMessage='想去苏州散步' /></MemoryRouter>)
  first.unmount()
  render(<MemoryRouter><DiscoveryPage /></MemoryRouter>)
  await screen.findByRole('button', { name: '了解公园' })
  expect(screen.getByRole('heading', { name: '想去苏州散步' })).toBeInTheDocument()
  expect(screen.getByRole('log')).toHaveTextContent('想去苏州散步')
  expect(post.mock.calls.some(([path]) => path === '/discovery/jobs')).toBe(false)
})
