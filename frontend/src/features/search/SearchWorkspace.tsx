import { useEffect, useLayoutEffect, useRef, useState } from 'react'

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
import { ResultList } from './ResultList'
import { QuerySummary } from './QuerySummary'
import { startSmoothScrollTo } from './scrolling'
import { TravelForm } from './TravelForm'
import {
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

export function SearchWorkspace({ initialMode, initialTarget }: SearchWorkspaceProps) {
  const { user } = useAuth()
  const [result, setResult] = useState<SearchResult | null>(() => loadSearchResult<SearchResult>())
  const [editingConditions, setEditingConditions] = useState(() => Boolean(initialTarget) || result === null)
  const [selectedId, setSelectedId] = useState<string | null>(loadSelectedPlaceId)
  const [submitting, setSubmitting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [favorites, setFavorites] = useState<Record<string, Favorite>>({})
  const [favoritePendingIds, setFavoritePendingIds] = useState<Set<string>>(new Set())
  const [transitioningToEdit, setTransitioningToEdit] = useState(false)
  const [landingAfterSubmit, setLandingAfterSubmit] = useState(false)
  const [scrollRequestVersion, setScrollRequestVersion] = useState(0)
  const submitLock = useRef(false)
  const controlsRef = useRef<HTMLDivElement>(null)
  const landingSummaryRef = useRef<HTMLDivElement>(null)
  const resultsRef = useRef<HTMLDivElement>(null)
  const pendingScrollRequest = useRef<{
    target: 'controls' | 'results' | 'landing'
    onComplete?: () => void
  } | null>(null)
  const preservedResultsTop = useRef<number | null>(null)
  const preservedSummaryTop = useRef<number | null>(null)

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

  useEffect(() => {
    const request = pendingScrollRequest.current
    if (!request) return
    pendingScrollRequest.current = null
    return startSmoothScrollTo(() => {
      if (request.target === 'controls') return controlsRef.current
      if (request.target === 'landing') return landingSummaryRef.current
      return resultsRef.current
    }, request.onComplete)
  }, [scrollRequestVersion])

  useLayoutEffect(() => {
    const summaryBeforeTop = preservedSummaryTop.current
    if (summaryBeforeTop !== null) {
      preservedSummaryTop.current = null
      const summaryAfterTop = controlsRef.current?.getBoundingClientRect().top
      if (summaryAfterTop !== undefined) {
        const layoutShift = summaryAfterTop - summaryBeforeTop
        if (Math.abs(layoutShift) > 1) {
          window.scrollTo({ top: Math.max(0, window.scrollY + layoutShift), behavior: 'auto' })
        }
      }
      return
    }

    const beforeTop = preservedResultsTop.current
    if (beforeTop === null) return
    preservedResultsTop.current = null
    const afterTop = resultsRef.current?.getBoundingClientRect().top
    if (afterTop === undefined) return
    const layoutShift = afterTop - beforeTop
    if (Math.abs(layoutShift) > 1) {
      window.scrollTo({ top: Math.max(0, window.scrollY + layoutShift), behavior: 'auto' })
    }
  }, [editingConditions, landingAfterSubmit])

  function requestSmoothScroll(target: 'controls' | 'results' | 'landing', onComplete?: () => void) {
    pendingScrollRequest.current = { target, onComplete }
    setScrollRequestVersion((current) => current + 1)
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
      setLandingAfterSubmit(true)
      requestSmoothScroll('landing', () => {
        preservedSummaryTop.current = landingSummaryRef.current?.getBoundingClientRect().top ?? null
        setLandingAfterSubmit(false)
        setEditingConditions(false)
      })
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

  function editConditions() {
    preservedResultsTop.current = resultsRef.current?.getBoundingClientRect().top ?? null
    setTransitioningToEdit(true)
    setEditingConditions(true)
    requestSmoothScroll('controls', () => {
      setTransitioningToEdit(false)
    })
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

  return (
    <div className={`search-workspace${result ? '' : ' search-workspace-empty'}`}>
      <div
        ref={controlsRef}
        className={`search-controls${editingConditions ? ' search-controls-editing' : ''}${landingAfterSubmit ? ' search-controls-landing' : ''}`}
      >
        {editingConditions ? (
          <TravelForm
            initialMode={initialMode}
            initialTarget={initialTarget}
            isSubmitting={submitting}
            fieldErrors={fieldErrors}
            onSubmit={submit}
          />
        ) : (
          <QuerySummary draft={loadTravelDraft()} onEdit={editConditions} />
        )}
        {landingAfterSubmit && (
          <div ref={landingSummaryRef} className="query-summary-landing">
            <QuerySummary draft={loadTravelDraft()} onEdit={editConditions} />
          </div>
        )}
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
        <div className={`workspace-message-slot${editingConditions ? '' : ' workspace-message-slot-collapsed'}`}>
          {error && <div className="error-banner" role="alert">{error}</div>}
        </div>
      </div>
      {status && <div className="app-toast" role="status">{status}</div>}
      {result && (
        <div ref={resultsRef} className="results-anchor">
          <ResultList
            items={items}
            source={result.source_state}
            generatedAt={result.generated_at}
            uncoveredTypes={uncoveredTypes}
            onFavorite={favorite}
            favoriteIds={new Set(Object.keys(favorites))}
            favoritePendingIds={favoritePendingIds}
            selectedId={activeSelectedId}
            onSelect={select}
            candidateSwitcherEnabled={!editingConditions && !transitioningToEdit}
          />
        </div>
      )}
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
