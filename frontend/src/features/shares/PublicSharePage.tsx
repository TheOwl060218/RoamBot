import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { apiClient } from '../../api/client'
import type { PublicSnapshot } from '../../api/types'
import { DailyWeatherList } from '../search/DailyWeatherList'
import { tripMatchIndex } from '../search/matchLabels'
import { DiscoveryArchiveCards } from '../discovery/DiscoveryArchiveCards'

const adviceLabels = {
  suitable: '适合前往',
  some_dates_caution: '部分日期需谨慎',
  some_dates_not_recommended: '部分日期不建议前往',
} as const

export function PublicSharePage() {
  const { token = '' } = useParams()
  const [snapshot, setSnapshot] = useState<PublicSnapshot | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    void apiClient.get<{ snapshot: PublicSnapshot }>(`/public/shares/${token}`)
      .then((response) => setSnapshot(response.snapshot))
      .catch(() => setUnavailable(true))
  }, [token])

  if (unavailable) return <section className="access-state"><h1>分享链接不可用或已撤销</h1></section>
  if (!snapshot) return <p className="loading-state">正在加载分享…</p>
  if (snapshot.mode === 'discovery') return <section className='public-share-page'>
    <header className='page-heading'><div><h1>{snapshot.city}休闲去处</h1></div>
      {snapshot.start_date && snapshot.end_date && <span>{snapshot.start_date} 至 {snapshot.end_date}</span>}
    </header><DiscoveryArchiveCards snapshot={snapshot} />
  </section>

  return (
    <section className="public-share-page">
      <header className="page-heading">
        <div><h1>{snapshot.city}出行结果</h1></div>
        <span>{snapshot.start_date} 至 {snapshot.end_date}</span>
      </header>
      <div className="personal-list">
        {snapshot.items.map((item, index) => (
          <article className="shared-result" key={`${item.destination.name}-${index}`}>
            <header>
              <div><p className="eyebrow">{item.destination.city}</p><h2>{item.destination.name}</h2><p>{item.destination.address}</p></div>
              <div className="match-index" aria-label={`出游匹配指数 ${tripMatchIndex(item.score.total)}`}>
                <strong>{tripMatchIndex(item.score.total)}</strong><span>出游匹配指数</span>
              </div>
            </header>
            <div className="shared-result-meta">
              <div>
                <span>地点评分</span>
                <strong>
                  {item.destination.rating === null
                    ? '暂无数据'
                    : `${item.destination.rating.toFixed(1)} / 5`}
                </strong>
              </div>
              <div>
                <span>出行建议</span>
                <strong>{adviceLabels[item.overall_advice]}</strong>
              </div>
            </div>
            <DailyWeatherList weather={item.weather} suitability={item.daily_suitability} />
            <div className="recommendation-copy">
              <h3>推荐理由</h3>
              <p>{item.explanation}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
