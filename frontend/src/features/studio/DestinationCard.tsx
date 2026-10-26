import type { RecommendationItem } from '../../api/types'
import { presentDestination } from './destinationPresentation'
import { sceneryLabels } from './conditionLabels'
export function DestinationCard({ item, all, selected, full, onOpen, onToggle, allowCandidate = true, teamMode = false }: {
  item: RecommendationItem; all: RecommendationItem[]; selected: boolean; full: boolean; onOpen: () => void; onToggle: () => void; allowCandidate?: boolean; teamMode?: boolean
}) {
  const p = presentDestination(item, all), d = item.destination
  return <article className='destination-card glass-panel' data-testid='destination-card' data-candidate-id={d.provider_id}>
    <button type='button' className='destination-card-open' onClick={onOpen} aria-label={`了解${d.name}`} />
    <div className='destination-card-top'><span>{d.scenery_tags.map(t => sceneryLabels[t]).join(' · ')}</span><strong aria-label={`出游匹配指数 ${p.index}`}>{p.index}<small>匹配指数</small></strong></div>
    <h2>{d.name}</h2><p className='destination-card-address'>{d.city} · {d.address}</p>
    <div className='destination-card-facts'><span>{p.weather}</span><span>平均 {item.group_accessibility.average_distance_km.toFixed(1)} km</span><span>{p.rating}</span></div>
    <div className='destination-traits'>{p.advantages.map(text => <span key={text}>{text}</span>)}</div>
    {p.tradeoffs.length > 0 && <p className='destination-tradeoff'>{p.tradeoffs.join(' · ')}</p>}
    {allowCandidate && <footer><button type='button' className='candidate-toggle' disabled={!selected && full} aria-pressed={selected} aria-label={`${selected ? '移出' : '加入'}候选：${d.name}`} onClick={onToggle}>{selected ? '已加入 ✓' : teamMode ? '放入同行清单 +' : '加入比较 +'}</button></footer>}
  </article>
}
