import { Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { apiClient, ApiError } from '../api/client'
import type { HistoryDetail, HistorySummary } from '../api/types'
import { ConfirmDialog } from '../app/ConfirmDialog'
import { HistoryList } from '../features/history/HistoryList'
import { restoreHistorySearch } from '../features/history/restoreHistorySearch'
import { useAuth } from '../features/auth/authContext'
import { useBusinessRevision } from '../features/commands/commandEvents'
import { useCommandTarget } from '../features/commands/commandContext'

export function HistoryPage() {
  const businessRevision = useBusinessRevision()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [histories, setHistories] = useState<HistorySummary[]>([])
  useCommandTarget('history-list', () => ({ visible_resources: {
    kind: 'history', ids: histories.slice(0, 100).map(item => item.id) } }), () => false)
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('')
  const [toast, setToast] = useState('')
  const [rerunningId, setRerunningId] = useState<string | null>(null)
  const rerunLock = useRef(false)
  const toastTimer = useRef<number | null>(null)
  const [confirmation, setConfirmation] = useState<{ kind: 'one'; id: string } | { kind: 'all' } | null>(null)

  useEffect(() => {
    void apiClient.get<{ histories: HistorySummary[] }>('/history')
      .then((response) => setHistories(response.histories))
      .catch(() => setStatus('历史加载失败，请稍后重试。'))
      .finally(() => setLoading(false))
  }, [businessRevision])

  useEffect(() => () => {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
  }, [])

  function showToast(message: string) {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current)
    setToast(message)
    toastTimer.current = window.setTimeout(() => setToast(''), 2600)
  }

  async function rerun(id: string) {
    if (rerunLock.current) return
    rerunLock.current = true
    setRerunningId(id)
    try {
      const response = await apiClient.post<{ history: HistoryDetail }>(`/history/${id}/rerun`)
      const restoredSearch = restoreHistorySearch(response.history, user?.username ?? null)
      navigate('/recommend', { state: { restoredSearch } })
    } catch (error) {
      setStatus(error instanceof ApiError && error.code === 'history_dates_expired'
        ? error.message : '重新查询失败。')
    } finally {
      rerunLock.current = false
      setRerunningId(null)
    }
  }

  async function remove(id: string) {
    setConfirmation({ kind: 'one', id })
  }

  async function confirmRemove(id: string) {
    setConfirmation(null)
    try {
      await apiClient.delete(`/history/${id}`)
      setHistories((current) => current.filter((history) => history.id !== id))
      showToast('历史已删除')
    } catch {
      setStatus('删除历史失败。')
    }
  }

  async function clear() {
    setConfirmation({ kind: 'all' })
  }

  async function confirmClear() {
    setConfirmation(null)
    try {
      await apiClient.delete('/history')
      setHistories([])
      showToast('历史已清空，相关分享链接也已失效。')
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
        <HistoryList
          histories={histories}
          onRerun={rerun}
          onDelete={remove}
          onStatus={showToast}
          rerunningId={rerunningId}
        />
      )}
      <ConfirmDialog
        open={confirmation !== null}
        title={confirmation?.kind === 'all' ? '清空全部历史？' : '删除这条历史？'}
        message={confirmation?.kind === 'all'
          ? '全部历史及其分享链接将失效，收藏地点不受影响。'
          : '这条历史及其分享链接将失效，收藏地点不受影响。'}
        confirmLabel={confirmation?.kind === 'all' ? '清空历史' : '删除历史'}
        onCancel={() => setConfirmation(null)}
        onConfirm={() => {
          if (confirmation?.kind === 'all') void confirmClear()
          else if (confirmation?.kind === 'one') void confirmRemove(confirmation.id)
        }}
      />
      {toast && <div className="app-toast" role="status">{toast}</div>}
    </section>
  )
}
