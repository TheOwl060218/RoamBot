import { CalendarDays, MapPin, Pencil, Route, Tags } from 'lucide-react'

import type { TravelFormDraft } from './formState'

type QuerySummaryProps = {
  draft: TravelFormDraft | null
  onEdit: () => void
}

const sceneryLabels = {
  lake: '湖景',
  sea: '海景',
  old_town: '古镇/历史街区',
  museum: '博物馆',
  park: '公园/绿地/湿地',
  mountain: '山地/徒步',
} as const

export function QuerySummary({ draft, onEdit }: QuerySummaryProps) {
  return (
    <section className="query-summary" aria-label="当前查询条件">
      <div className="query-summary-heading">
        <div>
          <p className="eyebrow">当前查询</p>
          <h1>{draft?.mode === 'place_evaluation' ? '评估指定地点' : '推荐出行地点'}</h1>
        </div>
        <button className="icon-text-button" type="button" onClick={onEdit}>
          <Pencil aria-hidden="true" size={16} />
          修改条件
        </button>
      </div>
      {draft ? (
        <div className="query-facts">
          <span><MapPin aria-hidden="true" size={16} />{draft.city} · {draft.mainOrigin}</span>
          <span><CalendarDays aria-hidden="true" size={16} />{formatDateRange(draft.startDate, draft.endDate)}</span>
          <span><Route aria-hidden="true" size={16} />{draft.maxDistance} km 内</span>
          <span><Tags aria-hidden="true" size={16} />{draft.mode === 'place_evaluation'
            ? draft.targetPlace
            : draft.sceneryTypes.map((type) => sceneryLabels[type]).join('、')}</span>
        </div>
      ) : (
        <p className="query-summary-fallback">已恢复上次查询结果。</p>
      )}
    </section>
  )
}

function formatDateRange(start: string, end: string) {
  const format = (value: string) => {
    const [, month, day] = value.split('-').map(Number)
    return `${month}月${day}日`
  }
  return start === end ? format(start) : `${format(start)} 至 ${format(end)}`
}
