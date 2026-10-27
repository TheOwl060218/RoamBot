import { render as renderView, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../src/api/client'
import { FavoritesPage } from '../src/pages/FavoritesPage'
import { HistoryPage } from '../src/pages/HistoryPage'
import { HistoryDetailPage } from '../src/pages/HistoryDetailPage'
import { PublicSharePage } from '../src/features/shares/PublicSharePage'
import { SearchPage } from '../src/pages/SearchPage'
import { AuthContext } from '../src/features/auth/authContext'

function render(ui: React.ReactNode) {
  return renderView(<AuthContext.Provider value={{ user: { username: 'owner' }, initializing: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}>{ui}</AuthContext.Provider>)
}

describe('personal and shared pages', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('reruns once and returns fresh results to the workspace even without session storage', async () => {
    sessionStorage.setItem('roambot.session.search-draft.v1', JSON.stringify({ mode: 'recommendation', city: '旧城市', mainOrigin: '旧出发地', companions: [], mainOriginCoordinate: null, companionOriginCoordinates: [], maxDistance: '50', startDate: '2026-11-01', endDate: '2026-11-01', sceneryTypes: ['lake'], matchMode: 'any', targetPlace: '' }))
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('disabled') })
    vi.spyOn(apiClient, 'get').mockImplementation(async path => path === '/history'
      ? { histories: [{ id: 'old', mode: 'recommendation', city: '杭州', start_date: '2026-12-01', end_date: '2026-12-01', item_count: 0, created_at: '2026-10-06' }] }
      : { favorites: [] })
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ history: { id: 'fresh', mode: 'recommendation',
      request: { city: '杭州', main_origin: '杭州东站', companion_origins: [], main_origin_coordinate: null, companion_origin_coordinates: [], max_distance_km: 35, start_date: '2026-12-01', end_date: '2026-12-01', scenery_types: ['museum'], scenery_match_mode: 'any', weights: { weather: 40, distance: 30, popularity: 30, fairness: 0 } },
      result: { items: [], source_state: { kind: 'demo', notices: [] }, generated_at: '2026-10-06', uncovered_scenery_types: [] }, snapshot: true } })
    render(<AuthContext.Provider value={{ user: { username: 'owner' }, initializing: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter initialEntries={['/history']}><Routes>
        <Route path='/history' element={<HistoryPage />} /><Route path='/recommend' element={<SearchPage />} />
        <Route path='/history/:id' element={<p>不应进入历史详情</p>} />
      </Routes></MemoryRouter></AuthContext.Provider>)
    await userEvent.click(await screen.findByRole('button', { name: '更多历史操作' }))
    await userEvent.click(screen.getByRole('button', { name: '重新查询' }))
    expect(await screen.findByRole('region', { name: '当前出行条件' })).toHaveTextContent('杭州东站')
    expect(document.querySelector('.studio-results')).toBeInTheDocument()
    expect(post).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledWith('/history/old/rerun')
    sessionStorage.clear()
  })

  it('failed rerun stays in history without clearing the current saved result', async () => {
    sessionStorage.setItem('roambot.session.search-result.v1', 'preserved')
    vi.spyOn(apiClient, 'get').mockResolvedValue({ histories: [{ id: 'old', mode: 'recommendation', city: '杭州', start_date: '2026-12-01', end_date: '2026-12-01', item_count: 0, created_at: '2026-10-06' }] })
    vi.spyOn(apiClient, 'post').mockRejectedValue(new Error('offline'))
    render(<MemoryRouter><HistoryPage /></MemoryRouter>)
    await userEvent.click(await screen.findByRole('button', { name: '更多历史操作' }))
    await userEvent.click(screen.getByRole('button', { name: '重新查询' }))
    expect(await screen.findByText('重新查询失败。')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '历史' })).toBeInTheDocument()
    expect(sessionStorage.getItem('roambot.session.search-result.v1')).toBe('preserved')
    sessionStorage.clear()
  })

  it('lists saved places without presenting stale scores', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      favorites: [
        {
          id: 'fav-1',
          created_at: '2026-07-17T09:00:00Z',
          place: {
            provider: 'amap',
            provider_place_id: 'jinji-lake',
            name: '金鸡湖景区',
            address: '苏州工业园区',
            city: '苏州',
            coordinate: { longitude: 120.7, latitude: 31.3, system: 'gcj02' },
            type_name: '风景名胜',
            type_code: '110000',
            scenery_tags: ['lake'],
          },
        },
        {
          id: 'fav-2',
          created_at: '2026-07-18T09:00:00Z',
          place: {
            provider: 'amap',
            provider_place_id: 'suzhou-museum',
            name: '苏州博物馆',
            address: '东北街204号',
            city: '苏州',
            coordinate: { longitude: 120.63, latitude: 31.32, system: 'gcj02' },
            type_name: '博物馆',
            type_code: '140100',
            scenery_tags: ['museum'],
          },
        },
      ],
    })

    function ReevaluateTarget() {
      const location = useLocation()
      return <p>{String((location.state as { initialIdea?: string } | null)?.initialIdea)}</p>
    }

    render(
      <MemoryRouter initialEntries={['/favorites']}>
        <Routes>
          <Route path="/favorites" element={<FavoritesPage />} />
          <Route path="/explore" element={<ReevaluateTarget />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('button', { name: '查看 金鸡湖景区' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('heading', { name: '金鸡湖景区' })).not.toBeInTheDocument()
    expect(screen.getAllByText('湖景')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: '查看 苏州博物馆' }))
    expect(screen.getByRole('heading', { name: '苏州博物馆' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '查看 苏州博物馆' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('link', { name: '继续探索' }))
    expect(screen.getByText('想去苏州苏州博物馆，看看怎样游玩')).toBeInTheDocument()
    expect(screen.queryByText(/推荐指数/)).not.toBeInTheDocument()
  })

  it('confirms favorite removal with the shared toast treatment', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      favorites: [{
        id: 'fav-1',
        created_at: '2026-07-17T09:00:00Z',
        place: {
          provider: 'amap',
          provider_place_id: 'jinji-lake',
          name: '金鸡湖景区',
          address: '苏州工业园区',
          city: '苏州',
          coordinate: { longitude: 120.7, latitude: 31.3, system: 'gcj02' },
          type_name: '风景名胜',
          type_code: '110000',
          scenery_tags: ['lake'],
        },
      }],
    })
    vi.spyOn(apiClient, 'delete').mockResolvedValueOnce(undefined)

    render(<MemoryRouter><FavoritesPage /></MemoryRouter>)
    await user.click(await screen.findByRole('button', { name: '查看 金鸡湖景区' }))
    await user.click(await screen.findByRole('button', { name: '删除 金鸡湖景区' }))

    expect(await screen.findByRole('status')).toHaveTextContent('已取消收藏金鸡湖景区')
  })

  it('shows history as snapshots and keeps public shares free of origin addresses', async () => {
    vi.spyOn(apiClient, 'get')
      .mockResolvedValueOnce({
        histories: [
          {
            id: 'history-1',
            mode: 'recommendation',
            city: '苏州',
            start_date: '2026-07-18',
            end_date: '2026-07-18',
            item_count: 2,
            generated_at: '2026-07-17T09:00:00Z',
            created_at: '2026-07-17T09:00:00Z',
          },
        ],
      })
      .mockResolvedValueOnce({
        snapshot: {
          mode: 'recommendation',
          city: '苏州',
          companion_count: 0,
          start_date: '2026-07-18',
          end_date: '2026-07-18',
          generated_at: '2026-07-17T09:00:00Z',
          items: [
            {
              destination: { name: '金鸡湖景区', address: '苏州工业园区', city: '苏州', scenery_tags: ['lake'], rating: 4.8 },
              weather: [],
              daily_suitability: [],
              score: { weather: 90, distance: 80, fairness: 100, popularity: 100, coverage_penalty: 0, total: 88 },
              explanation: '适合短途出游。',
              overall_advice: 'suitable',
            },
          ],
          uncovered_scenery_types: [],
        },
      })

    const historyView = render(<MemoryRouter><HistoryPage /></MemoryRouter>)
    expect(await screen.findByRole('heading', { name: '历史' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /地点推荐 · 苏州/ })).toHaveAttribute('href', '/history/history-1')
    expect(screen.queryByRole('button', { name: '创建分享' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '更多历史操作' }))
    expect(screen.getByRole('button', { name: '创建分享' })).toBeInTheDocument()
    expect(document.querySelector('.history-menu-backdrop')).toBeInTheDocument()
    historyView.unmount()

    render(
      <MemoryRouter initialEntries={['/share/public-token']}>
        <Routes><Route path="/share/:token" element={<PublicSharePage />} /></Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
    expect(screen.getByText('出游匹配指数')).toBeInTheDocument()
    expect(document.querySelector('.public-share-page .result-method-note')).not.toBeInTheDocument()
    expect(document.querySelector('.public-share-page .privacy-note')).not.toBeInTheDocument()
    expect(screen.queryByText('88.0')).not.toBeInTheDocument()
    expect(screen.queryByText(/主出发地|同行人出发地/)).not.toBeInTheDocument()
  })

  it('requires confirmation before deleting history and explains share invalidation', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockResolvedValue({
      histories: [{
        id: 'history-1',
        mode: 'recommendation',
        city: '苏州',
        start_date: '2026-07-18',
        end_date: '2026-07-18',
        item_count: 1,
        generated_at: '2026-07-17T09:00:00Z',
        created_at: '2026-07-17T09:00:00Z',
      }],
    })
    const remove = vi.spyOn(apiClient, 'delete').mockResolvedValue(undefined)
    render(<MemoryRouter><HistoryPage /></MemoryRouter>)
    await user.click(await screen.findByRole('button', { name: '更多历史操作' }))
    await user.click(screen.getByRole('button', { name: '更多操作' }))
    await user.click(await screen.findByRole('button', { name: '删除历史' }))

    expect(remove).not.toHaveBeenCalled()
    expect(screen.getByRole('alertdialog', { name: '删除这条历史？' })).toHaveTextContent('分享链接将失效')
    expect(screen.getByRole('alertdialog', { name: '删除这条历史？' })).toHaveTextContent('收藏地点不受影响')

    await user.click(within(screen.getByRole('alertdialog', { name: '删除这条历史？' })).getByRole('button', { name: '删除历史' }))

    expect(remove).toHaveBeenCalledWith('/history/history-1')
    expect(await screen.findByRole('status')).toHaveTextContent('历史已删除')
  })

  it('keeps share actions readable after creating a link', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      histories: [{
        id: 'history-1',
        mode: 'recommendation',
        city: '苏州',
        start_date: '2026-07-18',
        end_date: '2026-07-18',
        item_count: 1,
        generated_at: '2026-07-17T09:00:00Z',
        created_at: '2026-07-17T09:00:00Z',
      }],
    })
    vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
      share: { id: 'share-1', url: '/share/token', created_at: '2026-07-17T09:00:00Z' },
    })

    render(<MemoryRouter><HistoryPage /></MemoryRouter>)
    await user.click(await screen.findByRole('button', { name: '更多历史操作' }))
    await user.click(await screen.findByRole('button', { name: '创建分享' }))

    expect(screen.getByRole('button', { name: '复制分享链接' })).toBeVisible()
    expect(document.querySelector('.app-toast')).toHaveTextContent('分享链接已创建')
  })

  it('renders a private history snapshot detail', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue({
      history: {
        id: 'history-1',
        mode: 'recommendation',
        request: {},
        result: {
          items: [],
          source_state: { kind: 'demo', notices: [] },
          generated_at: '2026-07-17T09:00:00Z',
        },
        created_at: '2026-07-17T09:00:00Z',
        snapshot: true,
      },
    })

    render(
      <MemoryRouter initialEntries={['/history/history-1']}>
        <Routes><Route path="/history/:historyId" element={<HistoryDetailPage />} /></Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '历史推荐' })).toBeInTheDocument()
    expect(screen.getByText('演示数据')).toBeInTheDocument()
    expect(document.querySelector('.history-detail-heading')).toBeInTheDocument()
    expect(document.querySelector('.history-detail-share-slot')).toBeInTheDocument()
  })
})
