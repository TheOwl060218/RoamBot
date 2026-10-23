import type { PublicDiscoverySnapshot } from './snapshotTypes'
import '../../styles/discovery.css'

export function DiscoveryArchiveCards({ snapshot }: { snapshot: PublicDiscoverySnapshot }) {
  return <section className='discovery-rail' aria-label='分享的去处' tabIndex={0}>
    {snapshot.cards.map((card, index) => <article className='discovery-card glass-panel' key={index}>
      <p className='eyebrow'>{card.experience}</p><h2>{card.place.name}</h2>
      <p className='discovery-address'>{card.place.city} · {card.place.address}</p>
      <p className='discovery-reason'>{card.reason}</p>
      {card.weather?.map(day => <p className='discovery-facts' key={day.date}>{day.date} · {day.condition} · {day.temp_min_c}–{day.temp_max_c}°C</p>)}
      <footer>{card.sources.filter(source => source.url).map(source => <a key={source.id} href={source.url} target='_blank' rel='noreferrer'>{source.title || '推荐依据'}</a>)}</footer>
    </article>)}
  </section>
}
