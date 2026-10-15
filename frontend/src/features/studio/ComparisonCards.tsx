import { useRef } from 'react'
import type { RecommendationItem } from '../../api/types'
import { compareCandidates } from '../search/compareLogic'
export function ComparisonCards({ items, onClose }: { items: RecommendationItem[]; onClose: () => void }) {
  const ref = useRef<HTMLElement>(null)
  const comparison = compareCandidates(items, items[0]?.distances.length ?? 1)
  if (!comparison) return null
  return <section ref={ref} tabIndex={-1} className='studio-comparison glass-panel' aria-label='候选对比'>
    <header><h2>哪些更适合你们？</h2><button type='button' onClick={onClose} className='text-button'>收起对比</button></header>
    {comparison.conclusions.map(c => <p key={c}>{c}</p>)}
    <div className='comparison-card-grid'>{items.map(item => <article key={item.destination.provider_id}><h3>{item.destination.name}</h3><dl>
      {comparison.rows.filter(row => ['total','weather','avgDistance', ...(item.distances.length > 1 ? ['maxDistance','fairness'] : [])].includes(row.key)).map(row => {
        const v = row.values.find(v => v.providerId === item.destination.provider_id)?.value
        return <div key={row.key}><dt>{row.label}</dt><dd className={row.bestIds.includes(item.destination.provider_id) ? 'metric-best' : ''}>{v == null ? '暂无数据' : v.toFixed(1)}{row.key.includes('Distance') && v != null ? ' km' : ''}{row.bestIds.includes(item.destination.provider_id) ? row.bestIds.length > 1 ? ' · 并列' : ' · 更优' : ''}</dd></div>
      })}<div><dt>高德评分</dt><dd>{item.destination.rating == null ? '暂无评分' : `${item.destination.rating.toFixed(1)} / 5`}</dd></div>
    </dl></article>)}</div>
  </section>
}
