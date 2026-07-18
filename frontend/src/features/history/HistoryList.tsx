import { RefreshCcw, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { HistorySummary } from '../../api/types'
import { ShareActions } from './ShareActions'

type HistoryListProps = {
  histories: HistorySummary[]
  onRerun: (id: string) => void
  onDelete: (id: string) => void
}

export function HistoryList({ histories, onRerun, onDelete }: HistoryListProps) {
  if (!histories.length) return <p className="empty-state">还没有成功查询记录。</p>
  return (
    <div className="personal-list">
      {histories.map((history) => (
        <article className="personal-item" data-history-id={history.id} key={history.id}>
          <div>
            <p className="eyebrow">历史快照</p>
            <h2>{history.mode === 'recommendation' ? '地点推荐' : '指定地点评估'} · {history.city}</h2>
            <p>{history.start_date} 至 {history.end_date} · {history.item_count} 个结果</p>
            <time dateTime={history.created_at}>保存于 {new Date(history.created_at).toLocaleString('zh-CN')}</time>
          </div>
          <div className="item-actions">
            <Link className="icon-text-button link-button" to={`/history/${history.id}`}>查看快照</Link>
            <button className="icon-text-button" type="button" onClick={() => onRerun(history.id)}>
              <RefreshCcw aria-hidden="true" size={16} />重新查询
            </button>
            <ShareActions historyId={history.id} />
            <button className="icon-button" type="button" aria-label="删除历史" onClick={() => onDelete(history.id)}>
              <Trash2 aria-hidden="true" size={17} />
            </button>
          </div>
        </article>
      ))}
    </div>
  )
}
