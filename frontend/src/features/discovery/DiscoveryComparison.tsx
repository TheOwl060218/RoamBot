import type { DiscoveryCard } from './types'
import { activityLabel, placeArea, placeType, routeLabel, visitingFacts, weatherLabel } from './discoveryPresentation'

export function DiscoveryComparison({ cards, onOpen }: { cards: DiscoveryCard[]; onOpen: (id: string) => void }) {
  const rows = [
    { label: '体验方向', values: cards.map(activityLabel) },
    { label: '地点类型', values: cards.map(c => placeType(c.place.map_type)) },
    { label: '所在地区', values: cards.map(placeArea) },
    { label: '具体地址', values: cards.map(c => c.place.address) },
    ...['开放时间', '参考消费'].map(label => ({ label, values: cards.map(c => visitingFacts(c).find(r => r.label === label)?.value ?? '') })),
    { label: '到达方式', values: cards.map(routeLabel) },
    { label: '天气', values: cards.map(weatherLabel) },
  ].filter(row => row.values.some(Boolean))
  return <div className='discovery-compare-scroll' tabIndex={0} role='region' aria-label='地点信息对比'>
    <table className='discovery-compare-table'>
      <caption className='sr-only'>已选地点逐项对比</caption>
      <thead><tr><th scope='col'>比较项目</th>{cards.map(c => <th key={c.place.id} scope='col'><h3>{c.place.name}</h3>
        <button type='button' className='text-button' onClick={() => onOpen(c.place.id)}>查看详情</button></th>)}</tr></thead>
      <tbody>{rows.map(row => <tr key={row.label}><th scope='row'>{row.label}</th>{row.values.map((value, i) => <td key={cards[i].place.id}>{value || '—'}</td>)}</tr>)}</tbody>
    </table>
  </div>
}
