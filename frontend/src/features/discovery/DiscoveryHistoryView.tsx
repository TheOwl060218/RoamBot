import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '../../api/client'
import { ShareActions } from '../history/ShareActions'
import { DiscoveryPage } from '../../pages/DiscoveryPage'
import type { DiscoveryHistory } from './snapshotTypes'
import type { DiscoverySnapshot } from './types'

export function DiscoveryHistoryView({ history }: { history: DiscoveryHistory }) {
  const [snapshot, setSnapshot] = useState<DiscoverySnapshot | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    void apiClient.post<DiscoverySnapshot>(`/discovery/history/${history.id}/restore`)
      .then(value => { if (active) setSnapshot(value) })
      .catch(caught => { if (active) setError(caught instanceof Error ? caught.message : '历史不可用。') })
    return () => { active = false }
  }, [history.id])
  return <section className='discovery-history-view'>
    <header className='page-heading personal-page'><div>
      <time dateTime={history.created_at}>保存于 {new Date(history.created_at).toLocaleString('zh-CN')}</time></div>
      <div className='item-actions'><Link className='text-button' to='/history' viewTransition>返回历史</Link><ShareActions historyId={history.id} /></div>
    </header>
    {error && <p role='alert'>{error}</p>}
    {snapshot && <DiscoveryPage key={snapshot.id} initialSnapshot={snapshot} initialMessage={history.request.message} archiveHistoryId={history.id} />}
  </section>
}
