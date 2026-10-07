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
import type { RestoredHistorySearch } from '../history/restoreHistorySearch'
import { CreatePlanControl } from '../plans/CreatePlanControl'
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
import { RevealNotice } from '../../components/RevealNotice'
import { useRevealNotice } from '../../components/useRevealNotice'
import {
  HOME_RESET_REQUEST_EVENT,
  clearSearchResult,
  loadSearchResult,
  loadSelectedPlaceId,
  loadTravelDraft,
  saveSearchResult,
  saveSelectedPlaceId,
} from './formState'

export type SearchResult = (RecommendationResponse | PlaceEvaluationResponse) & {
  query_request?: RecommendationRequest | PlaceEvaluationRequest
  history_owner?: string | null
}

type SearchWorkspaceProps = {
  initialMode?: 'recommendation' | 'place_evaluation'
  initialTarget?: string
  restoredSearch?: RestoredHistorySearch
}

const MIN_SIDEBAR_WIDTH = 490
const MAX_SIDEBAR_WIDTH = 700

export function SearchWorkspace({ initialMode, initialTarget, restoredSearch }: SearchWorkspaceProps) {
  const { user } = useAuth()
  const [result, setResult] = useState<SearchResult | null>(() => restoredSearch?.result ?? loadSearchResult<SearchResult>())
  const [selectedId, setSelectedId] = useState<string | null>(() => restoredSearch
    ? ('items' in restoredSearch.result ? restoredSearch.result.items[0] : restoredSearch.result.item)?.destination.provider_id ?? null
    : loadSelectedPlaceId())
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
  const { notice: comparisonNotice, notify: notifyComparison, clear: clearComparisonNotice } = useRevealNotice()
  const revealComparison = useRef(false)
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
      const response = 'target_place' in request
        ? await apiClient.post<PlaceEvaluationResponse>('/place-evaluations', request)
        : await apiClient.post<RecommendationResponse>('/recommendations', request)
      const next: SearchResult = { ...response, query_request: request, history_owner: user?.username ?? null }
      setResult(next)
      saveSearchResult(next)
      const nextItems = 'items' in next ? next.items : [next.item]
      const firstId = nextItems[0]?.destination.provider_id ?? null
      setSelectedId(firstId)
      if (firstId) saveSelectedPlaceId(firstId)
      window.setTimeout(() => requestSummaryScroll(), 0)
      setProgress(100)
      return next
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
    clearComparisonNotice()
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
  const comparisonCount = comparisonState.selectedItems.length
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      if (comparisonCount < 2) clearComparisonNotice()
      else if (revealComparison.current) {
        notifyComparison(comparisonRef.current, '对比已准备好，点击「查看对比结果」查看')
      }
      revealComparison.current = false
    })
    return () => window.cancelAnimationFrame(frame)
  }, [comparisonCount, notifyComparison, clearComparisonNotice])
  function toggleComparison(id: string) {
    if (comparisonCount === 2 && comparisonState.selectedIds.includes(id)) clearComparisonNotice()
    revealComparison.current = comparisonCount === 1 && !comparisonState.selectedIds.includes(id)
    comparisonState.toggle(id)
  }

  return (
    <div className={`search-workspace${result ? ' search-workspace-with-result' : ' search-workspace-empty'}`}>
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
                initialDraft={restoredSearch?.draft}
                initialMode={initialMode}
                initialTarget={initialTarget}
                isSubmitting={submitting}
                fieldErrors={fieldErrors}
                onSubmit={async request => { await submit(request) }}
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
                <QuerySummary draft={restoredSearch && result === restoredSearch.result ? restoredSearch.draft : loadTravelDraft()} onEdit={editConditions} />
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
                  toggle={toggleComparison}
                  onViewComparison={viewComparison}
                />
              )}
              {comparisonState.selectedItems.length >= 2 && 'items' in result && result.query_request && !('target_place' in result.query_request) && (
                <CreatePlanControl
                  key={result.generated_at}
                  historyId={result.history_id ?? null}
                  trusted={Boolean(user && result.history_owner === user.username && result.history_id)}
                  selectedIds={comparisonState.selectedIds}
                  city={result.query_request.city}
                  startDate={result.query_request.start_date}
                  endDate={result.query_request.end_date}
                  originCount={1 + result.query_request.companion_origins.length}
                  onRerun={async () => {
                    const next = await submit(result.query_request!)
                    if (!next) throw new Error('重新推荐失败')
                    const nextIds = 'items' in next ? next.items.map(i => i.destination.provider_id) : []
                    if (!comparisonState.selectedIds.every(id => nextIds.includes(id))) {
                      comparisonState.reset()
                      setStatus('推荐已更新，请重新选择 2～3 个地点。')
                    } else setStatus('推荐已更新，可以继续创建同行计划了。')
                  }}
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
            <SampleScenes onExplore={async request => { await submit(request) }} />
          )}
        </div>
      </div>
      {status && <div className="app-toast" role="status">{status}</div>}
      <RevealNotice notice={comparisonNotice} />
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
