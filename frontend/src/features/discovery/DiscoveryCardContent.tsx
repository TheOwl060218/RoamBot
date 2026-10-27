import type { DiscoveryCard } from './types'
import { activityLabel, routeLabel, visitingFacts } from './discoveryPresentation'
import { WeatherStrip } from '../../components/WeatherStrip'

function cardReason(card: DiscoveryCard) {
  const reason = card.reason?.trim() ?? ''
  return reason && reason !== activityLabel(card) && reason !== card.place.name ? reason : ''
}

export function DiscoveryCardSummary({ card, expanded = false }: { card: DiscoveryCard; expanded?: boolean }) {
  const activity = activityLabel(card), reason = cardReason(card), route = routeLabel(card)
  return <div className='discovery-card-summary'>
    {activity && <p className='discovery-activity'>{activity}</p>}
    {reason && !expanded && <p className='discovery-card-reason'>{reason}</p>}
    {!expanded && card.place.address && <p className='discovery-card-location' title={card.place.address}>{card.place.address}</p>}
    {route && <p className='discovery-card-travel'>{route}</p>}
    {!expanded && <dl className='discovery-card-info discovery-place-facts'>
      {visitingFacts(card).map(row => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}
    </dl>}
  </div>
}

export function DiscoveryCardDetails({ card }: { card: DiscoveryCard }) {
  const facts = visitingFacts(card)
  const links = card.sources.flatMap(source => {
    try {
      const url = new URL(source.url ?? '')
      return ['https:', 'http:'].includes(url.protocol) ? [{ ...source, url: url.href, label: source.title?.trim() || url.hostname }] : []
    } catch { return [] }
  }).filter((source, index, all) => all.findIndex(item => item.url === source.url) === index)
  return <div className='discovery-detail-content'>
    {cardReason(card) && <p className='discovery-detail-reason'>{cardReason(card)}</p>}
    {card.place.address && <p className='discovery-address'>{card.place.address}</p>}
    {(facts.length > 0 || card.place.facts.tel) && <dl className='discovery-card-info discovery-place-facts'>
      {facts.map(row => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}
      {card.place.facts.tel && <div><dt>联系电话</dt><dd>{card.place.facts.tel}</dd></div>}
    </dl>}
    {Array.isArray(card.weather) && <WeatherStrip days={card.weather} />}
    {links.length > 0 && <details className='discovery-card-sources'><summary>资料来源 · {links.length}</summary>
      <ul>{links.map(source => <li key={source.url}><a href={source.url} target='_blank' rel='noopener noreferrer'>{source.label} ↗</a></li>)}</ul>
    </details>}
  </div>
}
