import { useState } from 'react'

import { ApiError, apiClient } from '../../api/client'
import type {
  PlaceEvaluationRequest,
  PlaceEvaluationResponse,
  RecommendationItem,
  RecommendationRequest,
  RecommendationResponse,
} from '../../api/types'
import { useAuth } from '../auth/authContext'
import { ResultList } from './ResultList'
import { TravelForm } from './TravelForm'

type SearchResult = RecommendationResponse | PlaceEvaluationResponse

type SearchWorkspaceProps = {
  initialMode?: 'recommendation' | 'place_evaluation'
  initialTarget?: string
}

export function SearchWorkspace({ initialMode, initialTarget }: SearchWorkspaceProps) {
  const { user } = useAuth()
  const [result, setResult] = useState<SearchResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  async function submit(request: RecommendationRequest | PlaceEvaluationRequest) {
    setSubmitting(true)
    setError('')
    setFieldErrors({})
    try {
      const next = 'target_place' in request
        ? await apiClient.post<PlaceEvaluationResponse>('/place-evaluations', request)
        : await apiClient.post<RecommendationResponse>('/recommendations', request)
      setResult(next)
    } catch (caught) {
      if (caught instanceof ApiError) {
        setFieldErrors(Object.fromEntries(caught.fields.map((field) => [field.path, field.message])))
        setError(errorMessage(caught))
      } else {
        setError('暂时无法完成查询，请稍后再试。')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const items = result ? ('items' in result ? result.items : [result.item]) : []

  async function favorite(item: RecommendationItem) {
    try {
      await apiClient.post('/favorites', {
        provider: result?.source_state.kind === 'demo' ? 'mock' : 'amap',
        destination: item.destination,
      })
      setStatus(`已收藏 ${item.destination.name}。`)
    } catch {
      setStatus('收藏失败，请稍后重试。')
    }
  }

  return (
    <div className="search-workspace">
      <TravelForm
        initialMode={initialMode}
        initialTarget={initialTarget}
        isSubmitting={submitting}
        fieldErrors={fieldErrors}
        onSubmit={submit}
      />
      {error && <div className="error-banner" role="alert">{error}</div>}
      {status && <div className="status-banner" role="status">{status}</div>}
      {result && (
        <ResultList
          items={items}
          source={result.source_state}
          generatedAt={result.generated_at}
          onFavorite={user ? favorite : undefined}
        />
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
