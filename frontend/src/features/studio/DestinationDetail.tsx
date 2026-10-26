import { useEffect, useRef } from 'react'
import type { RecommendationItem } from '../../api/types'
import { DailyWeatherList } from '../search/DailyWeatherList'
import { amapPlaceUrl, amapSearchUrl } from '../search/amapLink'
import { presentDestination } from './destinationPresentation'
import { AmapLogo } from '../../components/AmapLogo'
export function DestinationDetail({ item, selected, full, onClose, onSelect, onMap, onFavorite, favoritePending, isFavorite, allowCandidate = true, teamMode = false }: {
  item: RecommendationItem; selected: boolean; full: boolean; onClose: () => void; onSelect: () => void; onMap: () => void; onFavorite: () => void; favoritePending: boolean; isFavorite: boolean; allowCandidate?: boolean; teamMode?: boolean
}) {
  const heading = useRef<HTMLHeadingElement>(null), p = presentDestination(item, [item]), d = item.destination
  useEffect(() => { heading.current?.focus({ preventScroll: true }) }, [d.provider_id])
  return <section className='destination-detail glass-panel' data-detail-id={d.provider_id} role='region' aria-label={`${d.name}详情`}>
    <header><button type='button' className='text-button' onClick={onClose}>← 返回地点</button></header>
    <div className='detail-title-row'><h2 ref={heading} tabIndex={-1}>{d.name}</h2><span className='detail-index'><strong>{p.index}</strong><small>出游匹配指数</small></span></div><p>{d.city} · {d.address}</p>
    <div className='detail-actions'><button type='button' className='text-button' data-studio-map-trigger onClick={onMap}><AmapLogo />查看位置</button>{amapPlaceUrl(d.provider_id) && <a className='text-button' href={amapSearchUrl(d.name, d.city)} target='_blank' rel='noopener noreferrer'>打开高德 ↗</a>}<button className='text-button' type='button' disabled={favoritePending} aria-pressed={isFavorite} onClick={onFavorite}>{isFavorite ? '取消收藏' : '收藏地点'}</button>{allowCandidate && <button className='primary-button' type='button' disabled={!selected && full} onClick={onSelect}>{selected ? '移出候选' : teamMode ? '放入同行清单' : '加入比较'}</button>}</div>
    <div className='detail-overview'><article><small>天气适配</small><strong>{p.weather}</strong></article><article><small>平均路程</small><strong>{item.group_accessibility.average_distance_km.toFixed(1)} km</strong></article><article><small>地点评分</small><strong>{p.rating}</strong></article></div>
    <p className='detail-explanation'>{item.explanation}</p>
    <section className='detail-weather'><h3>逐日天气与提醒</h3><DailyWeatherList weather={item.weather} suitability={item.daily_suitability} /></section>
    <details open><summary>每位同行者的路程</summary><div className='detail-routes'>{item.distances.map((distance, i) => <p key={i}><strong>{distance.origin_label}</strong><span>{distance.distance_km.toFixed(2)} km{distance.duration_minutes != null ? ` · 约 ${Math.round(distance.duration_minutes)} 分钟` : ''}{distance.estimated ? ' · 直线估算' : ' · 驾车估算'}</span></p>)}</div></details>
    <details><summary>匹配指数如何计算</summary><p>本次综合分 {item.score.total.toFixed(1)}。天气 {item.score.weather.toFixed(1)}、路程 {item.score.distance.toFixed(1)}、热度 {item.score.popularity?.toFixed(1) ?? '暂无数据'}{item.distances.length > 1 ? `、公平性 ${item.score.fairness.toFixed(1)}` : ''}，按本次偏好加权。</p></details>
  </section>
}
