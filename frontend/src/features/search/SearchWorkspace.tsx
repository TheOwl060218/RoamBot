import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'

import { ApiError, apiClient } from '../../api/client'
import { requestAccountDialog } from '../../app/accountDialog'
import type {
  PlaceEvaluationRequest,
  PlaceEvaluationResponse,
  Favorite,
  RecommendationItem,
  RecommendationRequest,
  RecommendationResponse,
} from '../../api/types'
import { useAuth } from '../auth/authContext'
import {
  CandidateComparisonSelector,
  CandidateComparisonTable,
} from './CandidateComparison'
import { useCandidateComparison } from './useCandidateComparison'
import { CandidateList } from './CandidateList'
import { ResultList } from './ResultList'
import { QuerySummary } from './QuerySummary'
import { SampleScenes } from './SampleScenes'
import { startSmoothScrollInContainer, startSmoothScrollTo } from './scrolling'
import { TravelForm } from './TravelForm'
import {
  HOME_RESET_REQUEST_EVENT,
  clearSearchResult,
  loadSearchResult,
  loadSelectedPlaceId,
  loadTravelDraft,
  saveSearchResult,
  saveSelectedPlaceId,
} from './formState'

type SearchResult = RecommendationResponse | PlaceEvaluationResponse

type SearchWorkspaceProps = {
  initialMode?: 'recommendation' | 'place_evaluation'
  initialTarget?: string
}

const MIN_SIDEBAR_WIDTH = 490
const MAX_SIDEBAR_WIDTH = 700

export function SearchWorkspace({ initialMode, initialTarget }: SearchWorkspaceProps) {
  const { user } = useAuth()
  const [result, setResult] = useState<SearchResult | null>(() => loadSearchResult<SearchResult>())
  const [selectedId, setSelectedId] = useState<string | null>(loadSelectedPlaceId)
  const [submitting, setSubmitting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [favorites, setFavorites] = useState<Record<string, Favorite>>({})
  const [favoritePendingIds, setFavoritePendingIds] = useState<Set<string>>(new Set())
  const [sidebarWidth, setSidebarWidth] = useState(490)
  const [scrollToSummaryVersion, setScrollToSummaryVersion] = useState(0)
  const [comparisonHighlighted, setComparisonHighlighted] = useState(false)
  const submitLock = useRef(false)
  const sidebarResizing = useRef(false)
  const sidebarRef = useRef<HTMLElement>(null)
  const formRef = useRef<HTMLDivElement>(null)
  const summaryRef = useRef<HTMLDivElement>(null)
  const resultsRef = useRef<HTMLDivElement>(null)
  const comparisonRef = useRef<HTMLDivElement>(null)
  const comparisonHighlightTimer = useRef<number | null>(null)

  useEffect(() => {
    if (!submitting) return
    const timer = window.setInterval(() => {
      setProgress((current) => Math.min(88, current + Math.max(2, Math.round((88 - current) / 7))))
    }, 300)
    return () => window.clearInterval(timer)
  }, [submitting])

  useEffect(() => {
    if (!user) {
      const timer = window.setTimeout(() => setFavorites({}), 0)
      return () => window.clearTimeout(timer)
    }
    void apiClient.get<{ favorites: Favorite[] }>('/favorites').then((response) => {
      setFavorites(Object.fromEntries(response.favorites.map((favorite) => [favorite.place.provider_place_id, favorite])))
    }).catch(() => undefined)
  }, [user])

  useEffect(() => {
    if (!status) return
    const timer = window.setTimeout(() => setStatus(''), 2200)
    return () => window.clearTimeout(timer)
  }, [status])

  useEffect(() => () => {
    if (comparisonHighlightTimer.current !== null) {
      window.clearTimeout(comparisonHighlightTimer.current)
    }
  }, [])

  useEffect(() => {
    const resetToHome = () => {
      if (result) {
        setResult(null)
        setSelectedId(null)
        clearSearchResult()
      } else {
        setStatus('已经在首页啦')
      }
    }
    window.addEventListener(HOME_RESET_REQUEST_EVENT, resetToHome)
    return () => window.removeEventListener(HOME_RESET_REQUEST_EVENT, resetToHome)
  }, [result])

  useEffect(() => {
    if (scrollToSummaryVersion === 0) return
    const sidebar = sidebarRef.current
    const summary = summaryRef.current
    if (!sidebar || !summary) return
    return startSmoothScrollInContainer(sidebar, () => summaryRef.current)
  }, [scrollToSummaryVersion])

  function requestSummaryScroll() {
    setScrollToSummaryVersion((current) => current + 1)
  }

  async function submit(request: RecommendationRequest | PlaceEvaluationRequest) {
    if (submitLock.current) return
    submitLock.current = true
    setSubmitting(true)
    setProgress(8)
    setError('')
    setFieldErrors({})
    try {
      const next = 'target_place' in request
        ? await apiClient.post<PlaceEvaluationResponse>('/place-evaluations', request)
        : await apiClient.post<RecommendationResponse>('/recommendations', request)
      setResult(next)
      saveSearchResult(next)
      const nextItems = 'items' in next ? next.items : [next.item]
      const firstId = nextItems[0]?.destination.provider_id ?? null
      setSelectedId(firstId)
      if (firstId) saveSelectedPlaceId(firstId)
      window.setTimeout(() => requestSummaryScroll(), 0)
      setProgress(100)
    } catch (caught) {
      if (caught instanceof ApiError) {
        if (caught.status === 401) {
          setFieldErrors({})
          setError('请先登录后再进行查询。')
          requestAccountDialog()
        } else {
          setFieldErrors(Object.fromEntries(caught.fields.map((field) => [field.path, field.message])))
          setError(errorMessage(caught))
        }
      } else {
        setError('暂时无法完成查询，请稍后再试。')
      }
      setProgress(0)
    } finally {
      setSubmitting(false)
      submitLock.current = false
      window.setTimeout(() => setProgress(0), 350)
    }
  }

  const items = result ? ('items' in result ? result.items : [result.item]) : []
  const uncoveredTypes = result && 'uncovered_scenery_types' in result
    ? result.uncovered_scenery_types
    : []
  const activeSelectedId = items.some((item) => item.destination.provider_id === selectedId)
    ? selectedId
    : items[0]?.destination.provider_id ?? null

  function select(item: RecommendationItem) {
    const nextId = item.destination.provider_id
    setSelectedId(nextId)
    saveSelectedPlaceId(nextId)
  }

  function startSidebarResize(event: ReactPointerEvent) {
    event.preventDefault()
    sidebarResizing.current = true
    const startX = event.clientX
    const startWidth = sidebarWidth
    const onMove = (moveEvent: PointerEvent) => {
      if (!sidebarResizing.current) return
      const next = Math.min(Math.max(startWidth + (moveEvent.clientX - startX), MIN_SIDEBAR_WIDTH), MAX_SIDEBAR_WIDTH)
      setSidebarWidth(next)
    }
    const onUp = () => {
      sidebarResizing.current = false
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  function editConditions() {
    const sidebar = sidebarRef.current
    if (sidebar) {
      startSmoothScrollInContainer(sidebar, () => formRef.current)
    }
  }

  function viewComparison() {
    const target = comparisonRef.current
    if (!target) return
    const finish = () => {
      target.focus({ preventScroll: true })
      setComparisonHighlighted(true)
      if (comparisonHighlightTimer.current !== null) {
        window.clearTimeout(comparisonHighlightTimer.current)
      }
      comparisonHighlightTimer.current = window.setTimeout(() => {
        setComparisonHighlighted(false)
        comparisonHighlightTimer.current = null
      }, 1800)
    }
    const detailPane = target.closest<HTMLElement>('.detail-pane')
    const detailPaneScrolls = detailPane
      && /auto|scroll/.test(window.getComputedStyle(detailPane).overflowY)
      && detailPane.scrollHeight > detailPane.clientHeight
    if (detailPane && detailPaneScrolls) {
      startSmoothScrollInContainer(detailPane, () => comparisonRef.current, finish)
    } else {
      startSmoothScrollTo(() => comparisonRef.current, finish)
    }
  }

  async function favorite(item: RecommendationItem) {
    if (!user) {
      requestAccountDialog()
      return
    }
    const placeId = item.destination.provider_id
    if (favoritePendingIds.has(placeId)) return
    setFavoritePendingIds((current) => new Set(current).add(placeId))
    try {
      const existing = favorites[placeId]
      if (existing) {
        await apiClient.delete(`/favorites/${existing.id}`)
        setFavorites((current) => {
          const next = { ...current }
          delete next[placeId]
          return next
        })
        setStatus(`已取消收藏 ${item.destination.name}。`)
      } else {
        const response = await apiClient.post<{ favorite: Favorite }>('/favorites', {
          provider: result?.source_state.kind === 'demo' ? 'mock' : 'amap',
          destination: item.destination,
        })
        setFavorites((current) => ({ ...current, [placeId]: response.favorite }))
        setStatus(`已收藏 ${item.destination.name}。`)
      }
    } catch {
      setStatus('收藏操作失败，请稍后重试。')
    } finally {
      setFavoritePendingIds((current) => {
        const next = new Set(current)
        next.delete(placeId)
        return next
      })
    }
  }

  const comparisonState = useCandidateComparison(items)

  return (
    <div className={`search-workspace${result ? ' search-workspace-with-result' : ' search-workspace-empty'}`}>
      <section className="quick-start-guide" aria-labelledby="quick-start-title">
        <div className="quick-start-copy">
          <p className="eyebrow">快速开始</p>
          <h2 id="quick-start-title">三步找到适合这次出行的地方</h2>
          <p>从出发条件到候选对比，把天气、路程和同行人的需要放在一起考虑。</p>
        </div>
        <ol className="quick-start-steps">
          <li><span>1</span><strong>填写条件</strong><small>出发地、日期与偏好</small></li>
          <li><span>2</span><strong>查看推荐</strong><small>综合天气与路程筛选</small></li>
          <li><span>3</span><strong>对比后决定</strong><small>选择 2～3 个候选</small></li>
        </ol>
      </section>
      <div
        className="workspace-layout"
        style={{ ['--sidebar-width' as string]: `${sidebarWidth}px` }}
      >
        <aside
          ref={sidebarRef}
          className="workspace-sidebar"
          aria-label="查询与候选列表"
        >
          <div ref={formRef} className="search-form-anchor">
            <div className="search-controls">
              <TravelForm
                initialMode={initialMode}
                initialTarget={initialTarget}
                isSubmitting={submitting}
                fieldErrors={fieldErrors}
                onSubmit={submit}
              />
              {progress > 0 && (
                <div
                  className="search-progress"
                  role="progressbar"
                  aria-label="正在生成推荐"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={progress}
                >
                  <span style={{ width: `${progress}%` }} />
                </div>
              )}
              <div className="workspace-message-slot">
                {error && <div className="error-banner" role="alert">{error}</div>}
              </div>
            </div>
          </div>
          {result && (
            <div className="sidebar-result-stack">
              <div ref={summaryRef} className="sidebar-summary-anchor">
                <QuerySummary draft={loadTravelDraft()} onEdit={editConditions} />
              </div>
              {items.length > 0 && (
                <div className="sidebar-candidate-list">
                  <CandidateList
                    items={items}
                    selectedId={activeSelectedId ?? ''}
                    onSelect={select}
                  />
                </div>
              )}
              {comparisonState.canCompare && (
                <CandidateComparisonSelector
                  items={comparisonState.items}
                  selectedIds={comparisonState.selectedIds}
                  toggle={comparisonState.toggle}
                  onViewComparison={viewComparison}
                />
              )}
            </div>
          )}
        </aside>
        <div className="workspace-resizer" role="separator" aria-label="调整侧栏宽度" onPointerDown={startSidebarResize} />
        <div className="workspace-main" ref={resultsRef}>
          {result ? (
            <div className="results-anchor" key={result.generated_at}>
              <ResultList
                items={items}
                source={result.source_state}
                generatedAt={result.generated_at}
                comparison={comparisonState.result && comparisonState.selectedItems.length >= 2
                  ? (
                    <div
                      ref={comparisonRef}
                      className={`comparison-focus-target${comparisonHighlighted ? ' comparison-focus-highlight' : ''}`}
                      tabIndex={-1}
                    >
                      <CandidateComparisonTable
                        selectedItems={comparisonState.selectedItems}
                        result={comparisonState.result}
                      />
                    </div>
                  )
                  : undefined}
                uncoveredTypes={uncoveredTypes}
                onFavorite={favorite}
                favoriteIds={new Set(Object.keys(favorites))}
                favoritePendingIds={favoritePendingIds}
                selectedId={activeSelectedId}
                onSelect={select}
                candidateSwitcherEnabled
              />
            </div>
          ) : (
            <SampleScenes onExplore={submit} />
          )}
        </div>
      </div>
      {status && <div className="app-toast" role="status">{status}</div>}
    </div>
  )
}

function errorMessage(error: ApiError) {
  const messages: Record<string, string> = {
    origin_not_found: '无法识别出发地，请补充更完整的地址。',
    place_not_found: '没有找到这个目标地点，请检查名称。',
    provider_unavailable: '地点或天气服务暂时不可用，请稍后重试。',
    validation_error: '请检查表单中的输入。',
  }
  return messages[error.code] ?? '请求失败，请稍后重试。'
}
