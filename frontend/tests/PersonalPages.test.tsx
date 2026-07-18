import { render, screen } from '@testing-library/react'
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
    await userEvent.click(screen.getByRole('link', { name: '重新评估' }))
    expect(screen.getByText('金鸡湖景区')).toBeInTheDocument()
    expect(screen.queryByText(/推荐指数/)).not.toBeInTheDocument()
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
              destination: { name: '金鸡湖景区', address: '苏州工业园区', city: '苏州', scenery_tags: ['lake'] },
              weather: [],
              daily_suitability: [],
              score: { weather: 90, distance: 80, fairness: 100, popularity: 100, coverage_penalty: 0, total: 88 },
              explanation: '适合短途出游。',
            },
          ],
        },
      })

    const historyView = render(<MemoryRouter><HistoryPage /></MemoryRouter>)
    expect(await screen.findByText('历史快照')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '创建分享' })).toBeInTheDocument()
    historyView.unmount()

    render(
      <MemoryRouter initialEntries={['/share/public-token']}>
        <Routes><Route path="/share/:token" element={<PublicSharePage />} /></Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
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
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)

    render(<MemoryRouter><HistoryPage /></MemoryRouter>)
    await user.click(await screen.findByRole('button', { name: '删除历史' }))

    expect(remove).not.toHaveBeenCalled()
    expect(confirm).toHaveBeenCalledWith(expect.stringMatching(/分享链接.*失效.*收藏/))
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
  })
})
