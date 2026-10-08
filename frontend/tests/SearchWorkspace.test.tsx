import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const scrollMocks = vi.hoisted(() => ({
  startSmoothScrollInContainer: vi.fn(),
  startSmoothScrollTo: vi.fn(),
}))

vi.mock('../src/features/search/scrolling', () => ({
  startSmoothScrollInContainer: scrollMocks.startSmoothScrollInContainer,
  startSmoothScrollTo: scrollMocks.startSmoothScrollTo,
}))

import { ApiError, apiClient } from '../src/api/client'
import { AppShell } from '../src/app/AppShell'
import type { RecommendationResponse } from '../src/api/types'
import { AuthProvider } from '../src/features/auth/AuthProvider'
import { AuthContext } from '../src/features/auth/authContext'
import { SearchWorkspace } from '../src/features/search/SearchWorkspace'
import { ResultList } from '../src/features/search/ResultList'
import { saveSearchResult } from '../src/features/search/formState'

const response: RecommendationResponse = {
  generated_at: '2026-07-17T08:00:00Z',
  source_state: { kind: 'demo', notices: ['苏州内置演示数据'] },
  items: [
    {
      destination: {
        provider_id: 'jinji-lake',
        name: '金鸡湖景区',
        address: '苏州工业园区',
        city: '苏州',
        coordinate: { longitude: 120.7, latitude: 31.3, system: 'gcj02' },
        type_name: '风景名胜',
        type_code: '110000',
        scenery_tags: ['lake', 'park'],
        popularity_rank: 1,
        rating: 4.8,
      },
      distances: [
        { origin_label: '主出发地', distance_km: 12.34, duration_minutes: 25, estimated: false },
      ],
      group_accessibility: {
        average_distance_km: 12.34,
        max_distance_km: 12.34,
        distance_variance: 0,
        distance_stddev: 0,
        fairness_score: 100,
      },
      weather: [
        {
          date: '2026-07-18',
          condition: '晴',
          temp_min_c: 23,
          temp_max_c: 31,
          precipitation_mm: 0,
          wind_speed_kmh: 8,
          humidity_percent: 60,
          visibility_km: 20,
          uv_index: 5,
        },
      ],
      daily_suitability: [{
        date: '2026-07-18',
        score: 90,
        status: 'suitable',
        summary: '7月18日天气条件适合前往。',
        reasons: ['天气晴朗'],
      }],
      score: {
        weather: 90,
        distance: 75.3,
        fairness: 100,
        popularity: 100,
        coverage_penalty: 0,
        total: 86.59,
      },
      explanation: '天气和距离都适合短途出游。',
      overall_advice: 'suitable',
    },
  ],
  uncovered_scenery_types: [],
}

const multiItemResponse: RecommendationResponse = {
  generated_at: '2026-07-17T08:00:00Z',
  source_state: { kind: 'demo', notices: ['苏州内置演示数据'] },
  items: [
    response.items[0],
    {
      ...response.items[0],
      destination: {
        ...response.items[0].destination,
        provider_id: 'suzhou-museum',
        name: '苏州博物馆',
        address: '东北街204号',
        scenery_tags: ['museum' as const],
      },
      score: { ...response.items[0].score, total: 82.4 },
    },
  ],
  uncovered_scenery_types: [],
}

describe('SearchWorkspace', () => {
  beforeEach(() => {
    scrollMocks.startSmoothScrollInContainer.mockReset()
    scrollMocks.startSmoothScrollInContainer.mockImplementation((_container, _getTarget, onComplete) => {
      queueMicrotask(() => onComplete?.())
      return () => undefined
    })
    scrollMocks.startSmoothScrollTo.mockReset()
    scrollMocks.startSmoothScrollTo.mockImplementation((_getTarget, onComplete) => {
      queueMicrotask(() => onComplete?.())
      return () => undefined
    })
  })

  it('keeps the initial form visible and does not show the quick-start guide', () => {
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    render(<AuthProvider><SearchWorkspace /></AuthProvider>)

    expect(screen.getByLabelText('主出发地')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '三步找到适合这次出行的地方' })).not.toBeInTheDocument()
  })

  it('clicking the RoamBot brand preserves the recommendation state', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    saveSearchResult(response)
    const { container } = render(
      <AuthProvider>
        <MemoryRouter>
          <AppShell><SearchWorkspace /></AppShell>
        </MemoryRouter>
      </AuthProvider>,
    )

    expect(await screen.findByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
    expect(container.querySelector('.search-workspace')).not.toHaveClass('search-workspace-empty')

    await user.click(screen.getByRole('link', { name: 'RoamBot' }))

    expect(container.querySelector('.search-workspace')).not.toHaveClass('search-workspace-empty')
    expect(screen.getByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
  })

  it('clicking the 推荐 link resets to the initial recommendation state', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    saveSearchResult(response)
    const { container } = render(
      <AuthProvider>
        <MemoryRouter>
          <AppShell><SearchWorkspace /></AppShell>
        </MemoryRouter>
      </AuthProvider>,
    )

    expect(await screen.findByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: '推荐' }))

    await waitFor(() => expect(container.querySelector('.search-workspace')).toHaveClass('search-workspace-empty'))
    expect(screen.queryByRole('heading', { name: '金鸡湖景区' })).not.toBeInTheDocument()
  })

  it('navigating from /favorites via the brand lands on home without clearing saved results', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    saveSearchResult(response)
    render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/favorites']}>
          <AppShell>
            <Routes>
              <Route path="/" element={<p>Photo home</p>} />
              <Route path="/favorites" element={<p>Favorites placeholder</p>} />
            </Routes>
          </AppShell>
        </MemoryRouter>
      </AuthProvider>,
    )

    expect(screen.getByText('Favorites placeholder')).toBeInTheDocument()
    expect(screen.queryByLabelText('主出发地')).not.toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'RoamBot' }))

    expect(screen.getByText('Photo home')).toBeInTheDocument()
    expect(sessionStorage.getItem('roambot.session.search-result.v1')).not.toBeNull()
  })

  it('navigating from /favorites via the 推荐 link lands on a clean empty workspace', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    saveSearchResult(response)
    const { container } = render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/favorites']}>
          <AppShell>
            <Routes>
              <Route path="/recommend" element={<SearchWorkspace />} />
              <Route path="/favorites" element={<p>Favorites placeholder</p>} />
            </Routes>
          </AppShell>
        </MemoryRouter>
      </AuthProvider>,
    )

    await user.click(screen.getByRole('link', { name: '推荐' }))

    await waitFor(() => expect(screen.getByLabelText('主出发地')).toBeInTheDocument())
    expect(container.querySelector('.search-workspace')).toHaveClass('search-workspace-empty')
    expect(screen.queryByRole('heading', { name: '金鸡湖景区' })).not.toBeInTheDocument()
  })

  it('keeps the form visible and scrolls the sidebar to the query summary after submit', async () => {
    const user = userEvent.setup()
    let scrollContainer: HTMLElement | null = null
    let scrollTarget: HTMLElement | null = null
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    vi.spyOn(apiClient, 'post').mockResolvedValueOnce(response)
    scrollMocks.startSmoothScrollInContainer.mockImplementation((container, getTarget, onComplete) => {
      scrollContainer = container
      scrollTarget = getTarget()
      queueMicrotask(() => onComplete?.())
      return () => undefined
    })

    render(<AuthProvider><SearchWorkspace /></AuthProvider>)

    await user.type(screen.getByLabelText('主出发地'), '苏州站')
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))

    expect(await screen.findByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '开始推荐' })).toBeInTheDocument()
    await waitFor(() => expect(scrollMocks.startSmoothScrollInContainer).toHaveBeenCalledTimes(1))
    expect(scrollContainer).toHaveClass('workspace-sidebar')
    expect(scrollTarget).toHaveClass('sidebar-summary-anchor')
  })

  it('opens a requested place evaluation even when a previous result is cached', () => {
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    saveSearchResult(response)

    render(
      <AuthProvider>
        <SearchWorkspace initialMode="place_evaluation" initialTarget="金鸡湖景区" />
      </AuthProvider>,
    )

    expect(screen.getByRole('radio', { name: '评估指定地点' })).toBeChecked()
    expect(screen.getByLabelText('目标地点')).toHaveValue('金鸡湖景区')
    expect(screen.getByRole('button', { name: '评估这个地点' })).toBeInTheDocument()
  })

  it('submits the form and displays a complete recommendation result', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    vi.spyOn(apiClient, 'post').mockResolvedValueOnce(response)
    const { container } = render(<AuthProvider><SearchWorkspace /></AuthProvider>)

    expect(container.querySelector('.search-workspace')).toHaveClass('search-workspace-empty')

    await user.type(screen.getByLabelText('主出发地'), '苏州站')
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))

    expect(await screen.findByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
    expect(container.querySelector('.search-workspace')).not.toHaveClass('search-workspace-empty')
    expect(screen.getByLabelText('出游匹配指数 87')).toBeInTheDocument()
    expect(screen.getByText('演示数据')).toBeInTheDocument()
    expect(screen.getByText(/12.34 km/)).toBeInTheDocument()
    expect(screen.getByText(/天气条件适合前往/)).toBeInTheDocument()
    expect(screen.getByText('天气和距离都适合短途出游。')).toBeInTheDocument()
    expect(screen.getAllByText(/天气数据来自和风天气；地点评分来自高德开放平台/)).toHaveLength(1)
    expect(await screen.findByRole('button', { name: '重新查询' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '开始推荐' })).toBeInTheDocument()
    expect(container.querySelector('.workspace-message-slot')).not.toHaveClass('workspace-message-slot-collapsed')
    expect(container.querySelectorAll('.query-summary .query-facts svg')).toHaveLength(5)
    expect(screen.getByText('最大距离内不限省市')).toBeInTheDocument()
    expect(container.querySelectorAll('.place-detail')).toHaveLength(1)
  })

  it('keeps the favorite action visible for guests and opens the account dialog', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    saveSearchResult(response)

    render(
      <AuthProvider>
        <MemoryRouter>
          <AppShell><SearchWorkspace /></AppShell>
        </MemoryRouter>
      </AuthProvider>,
    )

    await user.click(screen.getByRole('button', { name: '收藏地点' }))

    expect(screen.getByRole('dialog', { name: '登录 RoamBot' })).toBeInTheDocument()
  })

  it('clears the loaded favorite state when the user logs out', async () => {
    saveSearchResult(response)
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      favorites: [{
        id: 'favorite-1',
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
        created_at: '2026-07-17T08:00:00Z',
      }],
    })
    const signedIn = {
      user: { username: 'tester' },
      initializing: false,
      login: vi.fn(async () => undefined),
      register: vi.fn(async () => undefined),
      logout: vi.fn(async () => undefined),
    }
    const { rerender } = render(
      <AuthContext.Provider value={signedIn}>
        <SearchWorkspace />
      </AuthContext.Provider>,
    )

    expect(await screen.findByRole('button', { name: '取消收藏' })).toBeInTheDocument()

    rerender(
      <AuthContext.Provider value={{ ...signedIn, user: null }}>
        <SearchWorkspace />
      </AuthContext.Provider>,
    )

    await waitFor(() => expect(screen.getByRole('button', { name: '收藏地点' })).toBeInTheDocument())
  })

  it('opens the account dialog and explains that login is required after a 401 submit', async () => {
    const user = userEvent.setup()
    sessionStorage.clear()
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    vi.spyOn(apiClient, 'post').mockRejectedValueOnce(
      new ApiError(401, 'unauthorized', 'Unauthorized.'),
    )

    render(
      <AuthProvider>
        <MemoryRouter>
          <AppShell><SearchWorkspace /></AppShell>
        </MemoryRouter>
      </AuthProvider>,
    )

    await user.type(screen.getByLabelText('主出发地'), '苏州站')
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))

    expect(await screen.findByRole('dialog', { name: '登录 RoamBot' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('请先登录后再进行查询。')
  })

  it('selects one candidate at a time while keeping the existing form in place', async () => {
    const user = userEvent.setup()
    const museum = {
      ...response.items[0],
      destination: {
        ...response.items[0].destination,
        provider_id: 'suzhou-museum',
        name: '苏州博物馆',
        address: '东北街204号',
        scenery_tags: ['museum' as const],
      },
      score: { ...response.items[0].score, total: 82.4 },
    }
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ ...response, items: [response.items[0], museum] })
    const { container } = render(<AuthProvider><SearchWorkspace /></AuthProvider>)

    await user.type(screen.getByLabelText('主出发地'), '苏州站')
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))

    const candidateNavigation = await screen.findByRole('navigation', { name: '候选地点' })
    const firstCandidate = within(candidateNavigation).getByRole('button', { name: /金鸡湖景区/ })
    expect(firstCandidate).toHaveAttribute('aria-current', 'true')
    await user.click(screen.getByRole('button', { name: /苏州博物馆/ }))

    expect(screen.getByRole('heading', { name: '苏州博物馆' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '金鸡湖景区' })).not.toBeInTheDocument()

    expect(screen.getByRole('button', { name: '开始推荐' })).toBeInTheDocument()
    expect(screen.getByDisplayValue('苏州站')).toBeInTheDocument()
    expect(container.querySelector('.search-controls')).not.toHaveClass('search-controls-editing')
  })

  it('scrolls the sidebar back to the persistent form when re-querying', async () => {
    const user = userEvent.setup()
    let scrollContainer: HTMLElement | null = null
    let scrollTarget: HTMLElement | null = null
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    saveSearchResult(response)
    scrollMocks.startSmoothScrollInContainer.mockImplementation((container, getTarget) => {
      scrollContainer = container
      scrollTarget = getTarget()
      return () => undefined
    })

    render(<AuthProvider><SearchWorkspace /></AuthProvider>)

    await user.click(screen.getByRole('button', { name: '重新查询' }))

    expect(screen.getByRole('button', { name: '开始推荐' })).toBeInTheDocument()
    expect(scrollContainer).toHaveClass('workspace-sidebar')
    expect(scrollTarget).toHaveClass('search-form-anchor')
  })

  it('locks repeated submissions immediately and shows non-numeric progress', async () => {
    const user = userEvent.setup()
    let resolveRequest!: (value: RecommendationResponse) => void
    const pending = new Promise<RecommendationResponse>((resolve) => {
      resolveRequest = resolve
    })
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    const post = vi.spyOn(apiClient, 'post').mockReturnValue(pending)
    post.mockClear()
    render(<AuthProvider><SearchWorkspace /></AuthProvider>)

    await user.type(screen.getByLabelText('主出发地'), '苏州站')
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    const button = screen.getByRole('button', { name: '开始推荐' })
    await user.dblClick(button)

    expect(post).toHaveBeenCalledTimes(1)
    const progress = screen.getByRole('progressbar', { name: '正在生成推荐' })
    expect(progress).toBeInTheDocument()
    expect(progress).toHaveTextContent('')

    resolveRequest(response)
    expect(await screen.findByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
  })

  it('offers mobile candidate navigation after the initial list leaves view', async () => {
    const user = userEvent.setup()
    const originalScrollY = Object.getOwnPropertyDescriptor(window, 'scrollY')
    const museum = {
      ...response.items[0],
      destination: {
        ...response.items[0].destination,
        provider_id: 'suzhou-museum-mobile',
        name: '苏州博物馆',
      },
    }

    try {
      const view = render(
        <ResultList
          items={[response.items[0], museum]}
          source={response.source_state}
          generatedAt={response.generated_at}
          candidateSwitcherEnabled={false}
        />,
      )

      Object.defineProperty(window, 'scrollY', { configurable: true, value: 160 })
      act(() => window.dispatchEvent(new Event('scroll')))

      expect(screen.queryByLabelText('切换候选地点')).not.toBeInTheDocument()
      view.rerender(
        <ResultList
          items={[response.items[0], museum]}
          source={response.source_state}
          generatedAt={response.generated_at}
          candidateSwitcherEnabled
        />,
      )
      act(() => window.dispatchEvent(new Event('scroll')))

      expect(screen.getByRole('button', { name: '上一个地点' })).toBeInTheDocument()
      expect(screen.getByLabelText('切换候选地点')).toHaveClass('candidate-switcher')
      await user.click(screen.getByRole('button', { name: /1\/2/ }))
      const drawer = screen.getByRole('dialog', { name: '选择候选地点' })
      expect(drawer).toBeInTheDocument()

      await user.click(within(drawer).getByRole('button', { name: /苏州博物馆/ }))
      expect(screen.getByRole('heading', { name: '苏州博物馆' })).toBeInTheDocument()
    } finally {
      if (originalScrollY) Object.defineProperty(window, 'scrollY', originalScrollY)
    }
  })

  it('renders the candidate comparison control after a multi-candidate search', async () => {
    const user = userEvent.setup()
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    vi.spyOn(apiClient, 'post').mockResolvedValueOnce(multiItemResponse)
    render(<AuthProvider><SearchWorkspace /></AuthProvider>)

    await user.type(screen.getByLabelText('主出发地'), '苏州站')
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))

    expect(await screen.findByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: '选择候选进行对比' })).toBeInTheDocument()
  })

  it('announces offscreen comparison only when the second candidate first makes it available', async () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ top: 2000, bottom: 2100, left: 0, right: 300, width: 300, height: 100 } as DOMRect)
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    saveSearchResult(multiItemResponse)
    render(<AuthProvider><SearchWorkspace /></AuthProvider>)
    const choices = within(screen.getByRole('group', { name: '选择候选进行对比' })).getAllByRole('checkbox')
    await userEvent.click(choices[0])
    expect(screen.queryByText(/对比已准备好/)).not.toBeInTheDocument()
    await userEvent.click(choices[1])
    expect(await screen.findByText(/对比已准备好/)).toBeInTheDocument()
    await userEvent.click(choices[1])
    expect(screen.queryByText(/对比已准备好/)).not.toBeInTheDocument()
  })

  it('takes users to the highlighted comparison after two candidates are selected', async () => {
    const user = userEvent.setup()
    let scrollTarget: HTMLElement | null = null
    vi.spyOn(apiClient, 'me').mockResolvedValueOnce(null)
    vi.spyOn(apiClient, 'post').mockResolvedValueOnce(multiItemResponse)
    scrollMocks.startSmoothScrollTo.mockImplementation((getTarget, onComplete) => {
      scrollTarget = getTarget()
      queueMicrotask(() => onComplete?.())
      return () => undefined
    })
    render(<MemoryRouter><AuthProvider><SearchWorkspace /></AuthProvider></MemoryRouter>)

    await user.type(screen.getByLabelText('主出发地'), '苏州站')
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))
    await screen.findByRole('heading', { name: '金鸡湖景区' })

    const comparisonGroup = screen.getByRole('group', { name: '选择候选进行对比' })
    const choices = within(comparisonGroup).getAllByRole('checkbox')
    await user.click(choices[0])
    await user.click(choices[1])
    expect(within(screen.getByRole('complementary', { name: '查询与候选列表' }))
      .getByRole('button', { name: '创建同行计划' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '查看对比结果（2）' }))

    await waitFor(() => expect(scrollMocks.startSmoothScrollTo).toHaveBeenCalledTimes(1))
    expect(scrollTarget).toHaveClass('comparison-focus-target')
    await waitFor(() => expect(scrollTarget).toHaveFocus())
    expect(scrollTarget).toHaveClass('comparison-focus-highlight')
  })
})
