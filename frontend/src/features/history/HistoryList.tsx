import { Link } from 'react-router-dom'

import type { HistorySummary } from '../../api/types'
import { HistoryActionsMenu } from './HistoryActionsMenu'

type HistoryListProps = {
  histories: HistorySummary[]
  onRerun: (id: string) => void
  onDelete: (id: string) => void
  rerunningId?: string | null
  onStatus: (message: string) => void
}

export function HistoryList({ histories, onRerun, onDelete, onStatus, rerunningId = null }: HistoryListProps) {
  if (!histories.length) return <p className="empty-state">还没有成功查询记录。</p>
  return (
    <div className="personal-list">
      {histories.map((history) => (
        <article className="history-row" data-history-id={history.id} key={history.id}>
          <Link className="history-row-main" to={`/history/${history.id}`}>
            <p className="eyebrow">历史快照</p>
            <h2>{history.mode === 'recommendation' ? '地点推荐' : '指定地点评估'} · {history.city}</h2>
            <p>{history.start_date} 至 {history.end_date} · {history.item_count} 个结果</p>
            <time dateTime={history.created_at}>保存于 {new Date(history.created_at).toLocaleString('zh-CN')}</time>
          </Link>
          <HistoryActionsMenu
            historyId={history.id}
            rerunning={rerunningId === history.id}
            rerunDisabled={rerunningId !== null}
            onRerun={() => onRerun(history.id)}
            onDelete={() => onDelete(history.id)}
            onStatus={onStatus}
          />
        </article>
      ))}
    </div>
  )
}
