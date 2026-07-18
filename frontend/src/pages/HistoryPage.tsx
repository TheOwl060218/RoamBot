import { Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { apiClient } from '../api/client'
import type { HistoryDetail, HistorySummary } from '../api/types'
import { HistoryList } from '../features/history/HistoryList'

export function HistoryPage() {
  const navigate = useNavigate()
  const [histories, setHistories] = useState<HistorySummary[]>([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('')

  useEffect(() => {
    void apiClient.get<{ histories: HistorySummary[] }>('/history')
      .then((response) => setHistories(response.histories))
      .catch(() => setStatus('历史加载失败，请稍后重试。'))
      .finally(() => setLoading(false))
  }, [])

  async function rerun(id: string) {
    try {
      const response = await apiClient.post<{ history: HistoryDetail }>(`/history/${id}/rerun`)
      navigate(`/history/${response.history.id}`)
    } catch {
      setStatus('重新查询失败。')
    }
  }

  async function remove(id: string) {
    if (!window.confirm('删除这条历史后，相关分享链接将失效；收藏地点不受影响。是否继续？')) return
    try {
      await apiClient.delete(`/history/${id}`)
      setHistories((current) => current.filter((history) => history.id !== id))
    } catch {
      setStatus('删除历史失败。')
    }
  }

  async function clear() {
    if (!window.confirm('清空全部历史后，所有相关分享链接都将失效；收藏地点不受影响。是否继续？')) return
    try {
      await apiClient.delete('/history')
      setHistories([])
      setStatus('历史已清空，相关分享链接也已失效。')
    } catch {
      setStatus('清空历史失败。')
    }
  }

  return (
    <section className="personal-page">
      <header className="page-heading">
        <div><p className="eyebrow">不可变结果记录</p><h1>历史</h1></div>
        {histories.length > 0 && (
          <button className="icon-text-button" type="button" onClick={clear}><Trash2 aria-hidden="true" size={16} />清空历史</button>
        )}
      </header>
      {status && <div className="status-banner" role="status">{status}</div>}
      {loading ? <p className="loading-state">正在加载历史…</p> : (
        <HistoryList histories={histories} onRerun={rerun} onDelete={remove} />
      )}
    </section>
  )
}
