import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { apiClient } from '../api/client'
import type { HistoryDetail, RecommendationItem } from '../api/types'
import { ShareActions } from '../features/history/ShareActions'
import { ResultList } from '../features/search/ResultList'

export function HistoryDetailPage() {
  const { historyId = '' } = useParams()
  const [history, setHistory] = useState<HistoryDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    void apiClient.get<{ history: HistoryDetail }>(`/history/${historyId}`)
      .then((response) => setHistory(response.history))
      .catch(() => setError('历史快照不可用或已被删除。'))
  }, [historyId])

  if (error) return <div className="error-banner" role="alert">{error}</div>
  if (!history) return <p className="loading-state">正在加载历史快照…</p>

  const result = history.result
  const items: RecommendationItem[] = 'items' in result ? result.items : [result.item]

  return (
    <section className="personal-page history-detail">
      <header className="page-heading">
        <div>
          <p className="eyebrow">不可变结果记录</p>
          <h1>历史快照</h1>
          <time dateTime={history.created_at}>
            保存于 {new Date(history.created_at).toLocaleString('zh-CN')}
          </time>
        </div>
        <div className="item-actions">
          <Link className="icon-text-button link-button" to="/history">
            <ArrowLeft aria-hidden="true" size={16} />返回历史
          </Link>
          <ShareActions historyId={history.id} />
        </div>
      </header>
      <ResultList
        items={items}
        source={result.source_state}
        generatedAt={result.generated_at}
      />
    </section>
  )
}
