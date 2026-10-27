import { CalendarDays, MapPin, Pencil, Route, Tags } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { RecommendationRequest, PlaceEvaluationRequest } from '../../api/types'
import { draftFromRequest } from './formState'
import { loadRegionCatalog } from './regions'

import type { TravelFormDraft } from './formState'

type QuerySummaryProps = {
  draft: TravelFormDraft | null
  request?: RecommendationRequest | PlaceEvaluationRequest
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

function RegionNames({ codes }: { codes: string[] }) {
  const [names, setNames] = useState<string[] | null>(null)
  useEffect(() => {
    let alive = true
    if (codes.length) void loadRegionCatalog().then((catalog) => {
      if (alive) setNames(codes.map((code) => catalog.regions.find((row) => row.adcode === code)?.name ?? '地区信息待确认'))
    }).catch(() => { if (alive) setNames(['地区信息待确认']) })
    return () => { alive = false }
  }, [codes])
  return <span><MapPin aria-hidden="true" size={16} />{codes.length ? names?.join('、') ?? '正在读取目的地范围…' : '最大距离内不限省市'}</span>
}

export function QuerySummary({ draft: storedDraft, request, onEdit }: QuerySummaryProps) {
  const draft = request ? draftFromRequest(request) : storedDraft
  return (
    <section className="query-summary" aria-label="当前查询条件">
      <div className="query-summary-heading">
        <div>
          
          <h1>{draft?.mode === 'place_evaluation' ? '评估指定地点' : '推荐出行地点'}</h1>
        </div>
        <button className="icon-text-button" type="button" onClick={onEdit}>
          <Pencil aria-hidden="true" size={16} />
          重新查询
        </button>
      </div>
      {draft ? (
        <div className="query-facts">
          <span><MapPin aria-hidden="true" size={16} />{draft.mainOrigin}</span>
          <span><CalendarDays aria-hidden="true" size={16} />{formatDateRange(draft.startDate, draft.endDate)}</span>
          {!(draft.mode === 'recommendation' && request && draft.destinationRegions?.length) &&
            <span><Route aria-hidden="true" size={16} />{draft.maxDistance} km 内</span>}
          {draft.mode === 'recommendation' && (request
            ? <RegionNames key={(draft.destinationRegions ?? []).join(',')} codes={draft.destinationRegions ?? []} />
            : <span>旧结果未记录目的地范围</span>)}
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
