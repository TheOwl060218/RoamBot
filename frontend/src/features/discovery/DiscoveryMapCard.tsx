import { useId, useState } from 'react'
import { ChevronDown, ExternalLink, MapPin } from 'lucide-react'
import type { DiscoveryCard } from './types'
import { placeArea, placeType } from './discoveryPresentation'
import { DiscoveryCardSummary, DiscoveryCardDetails } from './DiscoveryCardContent'
import { DiscoveryFavoriteControl } from './DiscoveryFavoriteControl'
import { AddToItinerary } from '../itineraries/ItineraryProvider'
import { amapSearchUrl } from '../search/amapLink'
import { PlaceTypeArtwork } from '../../components/PlaceTypeArtwork'
import { PlaceGuideLink } from '../../components/PlaceGuideLink'

export function DiscoveryMapCard({ card, jobId, source }: { card: DiscoveryCard; jobId: string; source: 'live' | 'demo' }) {
  const [expanded, setExpanded] = useState(false)
  const detailsId = useId()
  return <article className='discovery-map-card' aria-label={`${card.place.name}推荐卡片`}>
    <header><span className='discovery-experience'>{placeType(card.place.map_type) || card.place.city}</span>
      <DiscoveryFavoriteControl card={card} source={source} compact /></header>
    <h3>{card.place.name}</h3>
    <p className='discovery-card-city'><MapPin size={13} aria-hidden='true' />{placeArea(card)}</p>
    <DiscoveryCardSummary card={card} expanded={expanded} />
    <div className='discovery-map-card-actions'>
      <AddToItinerary source={{ source_job_id: jobId, place_id: card.place.id }} />
      <button type='button' className='text-button' aria-expanded={expanded} aria-controls={detailsId}
        onClick={() => setExpanded(value => !value)}>{expanded ? '收起卡片' : '展开卡片'}<ChevronDown size={14} aria-hidden='true' /></button>
    </div>
    <div id={detailsId} hidden={!expanded} className='discovery-map-card-details'>
      {expanded && <><DiscoveryCardDetails card={card} /><PlaceTypeArtwork typeName={card.place.map_type} />
        <div className='discovery-map-card-actions'><PlaceGuideLink name={card.place.name} city={card.place.city} /></div></>}
    </div>
    <a className='text-button discovery-map-external' href={amapSearchUrl(card.place.name, card.place.city)} target='_blank' rel='noopener noreferrer'>
      <ExternalLink size={14} aria-hidden='true' />打开高德</a>
  </article>
}
