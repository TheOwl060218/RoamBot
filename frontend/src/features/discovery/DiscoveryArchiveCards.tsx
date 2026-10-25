import type { PublicDiscoverySnapshot } from './snapshotTypes'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { X } from 'lucide-react'
import { DiscoveryRail } from './DiscoveryRail'
import { placeType } from './discoveryPresentation'
import { OverlayHost } from '../studio/OverlayHost'
import { amapSearchUrl } from '../search/amapLink'
import '../../styles/discovery.css'

export function DiscoveryArchiveCards({ snapshot }: { snapshot: PublicDiscoverySnapshot }) {
  const [selected, setSelected] = useState<number | null>(null)
  const card = selected === null ? null : snapshot.cards[selected]
  return <><DiscoveryRail label='分享的去处'>
    {snapshot.cards.map((card, index) => <article className='discovery-card glass-panel' key={index}>
      <button type='button' className='discovery-card-open' aria-label={`了解${card.place.name}`} onClick={() => setSelected(index)} />
      <div className='discovery-card-heading'><span className='discovery-experience'>{placeType(card.place.map_type)}</span><span className='discovery-card-number'>{String(index + 1).padStart(2, '0')}</span></div><h2>{card.place.name}</h2>
      <p className='discovery-activity'>{card.experience}</p>
      <p className='discovery-address'>{card.place.city} · {card.place.address}</p>
      {card.weather?.map(day => <p className='discovery-facts' key={day.date}>{day.date} · {day.condition} · {day.temp_min_c}–{day.temp_max_c}°C</p>)}
      <footer><a className='text-button' href={amapSearchUrl(card.place.name, card.place.city)} target='_blank' rel='noreferrer'>查看位置 ↗</a></footer>
    </article>)}
  </DiscoveryRail>
    <Link className='text-button' to='/explore' viewTransition>我也想找些去处</Link>
    {card && <OverlayHost label={`${card.place.name}详情`} onClose={() => setSelected(null)} panelClassName='discovery-detail glass-panel'>
      <button className='icon-button discovery-close' type='button' aria-label='关闭详情' onClick={() => setSelected(null)}><X size={18} /></button>
      <p className='eyebrow'>{card.experience}</p><h2>{card.place.name}</h2><p>{card.place.city} · {card.place.address}</p>
      <p>{placeType(card.place.map_type)}</p>
      {card.weather?.map(day => <p key={day.date}>{day.date} · {day.condition} · {day.temp_min_c}–{day.temp_max_c}°C</p>)}
      <div className='item-actions'><a className='text-button' href={amapSearchUrl(card.place.name, card.place.city)} target='_blank' rel='noreferrer'>查看位置 ↗</a>
        <Link className='text-button' viewTransition to='/explore' state={{ initialIdea: `想去${card.place.city}${card.place.name}，看看怎样游玩` }}>继续探索</Link></div>
    </OverlayHost>}
  </>
}
