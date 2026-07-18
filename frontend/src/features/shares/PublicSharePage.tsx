import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { apiClient } from '../../api/client'
import type { PublicSnapshot } from '../../api/types'
import { DailyWeatherList } from '../search/DailyWeatherList'

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
  if (!snapshot) return <p className="loading-state">正在加载分享快照…</p>

  return (
    <section className="public-share-page">
      <header className="page-heading">
        <div><p className="eyebrow">RoamBot 匿名分享</p><h1>{snapshot.city}出行结果</h1></div>
        <span>{snapshot.start_date} 至 {snapshot.end_date}</span>
      </header>
      <p className="privacy-note">该页面只包含脱敏后的地点、天气和评分，不包含账户身份与出发地址。</p>
      <div className="personal-list">
        {snapshot.items.map((item, index) => (
          <article className="shared-result" key={`${item.destination.name}-${index}`}>
            <header><div><p className="eyebrow">{item.destination.city}</p><h2>{item.destination.name}</h2><p>{item.destination.address}</p></div><strong>{item.score.total.toFixed(1)}</strong></header>
            <DailyWeatherList weather={item.weather} suitability={item.daily_suitability} />
            <p>{item.explanation}</p>
          </article>
        ))}
      </div>
    </section>
  )
}
