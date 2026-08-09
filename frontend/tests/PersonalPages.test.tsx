import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '../src/api/client'
import { FavoritesPage } from '../src/pages/FavoritesPage'
import { HistoryPage } from '../src/pages/HistoryPage'
import { HistoryDetailPage } from '../src/pages/HistoryDetailPage'
import { PublicSharePage } from '../src/features/shares/PublicSharePage'

describe('personal and shared pages', () => {
  beforeEach(() => vi.restoreAllMocks())

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
      return <p>{String((location.state as { evaluationTarget?: string } | null)?.evaluationTarget)}</p>
    }

    render(
      <MemoryRouter initialEntries={['/favorites']}>
        <Routes>
          <Route path="/favorites" element={<FavoritesPage />} />
          <Route path="/" element={<ReevaluateTarget />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
    expect(screen.getAllByText('苏州 · 湖景')).toHaveLength(2)
    expect(screen.getByRole('button', { name: '查看 金鸡湖景区' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: '查看 苏州博物馆' }))
    expect(screen.getByRole('heading', { name: '苏州博物馆' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '查看 苏州博物馆' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('link', { name: '重新评估' }))
    expect(screen.getByText('苏州博物馆')).toBeInTheDocument()
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
    expect(await screen.findByText('历史快照')).toBeInTheDocument()
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
    expect(screen.getAllByText(/地点评分数据来源：高德开放平台；出游匹配指数仅用于比较本次候选地点/)).toHaveLength(1)
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

    expect(screen.queryByRole('button', { name: '复制分享链接' })).not.toBeInTheDocument()
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

    expect(await screen.findByRole('heading', { name: '历史快照' })).toBeInTheDocument()
    expect(screen.getByText('演示数据')).toBeInTheDocument()
    expect(document.querySelector('.history-detail-heading')).toBeInTheDocument()
    expect(document.querySelector('.history-detail-share-slot')).toBeInTheDocument()
  })
})
