import type { ConditionCard, ResultRailCard, StudioState } from './types'
import { sceneryLabels } from './conditionLabels'

export function projectConditionCards(state: StudioState): ConditionCard[] {
  const d = state.draft, cards: ConditionCard[] = []
  function add(key: ConditionCard['key'], label: string, value: string, supplemental = false) {
    if (value.trim()) cards.push({ id: key, key, label, value, supplemental })
  }
  add('mainOrigin', '出发地', d.mainOrigin)
  add('dates', '日期', d.startDate ? `${d.startDate.slice(5)} → ${d.endDate.slice(5)}` : '')
  add('range', '目的地范围', d.destinationRegions?.length ? d.destinationRegions.join(' · ') : state.confirmedFields.includes('range') ? `${d.maxDistance} km 内` : '')
  if (d.mode === 'place_evaluation') add('targetPlace', '想评估的地点', d.targetPlace)
  else add('sceneryTypes', '想找的地方', d.sceneryQuery || d.sceneryTypes.map(t => sceneryLabels[t]).join(' · '))
  add('companions', '同行出发地', d.companions.join(' · '), true)
  add('weights', '推荐偏好', d.weights ? `天气 ${Math.round(d.weights.weather)} · 路程 ${Math.round(d.weights.distance)}` : '', true)
  return cards.slice(0, 8)
}

export function projectResultRail(cards: ConditionCard[]): ResultRailCard[] {
  const core = cards.filter(c => !c.supplemental).slice(0, 4)
  const rest = cards.filter(c => c.supplemental)
  return rest.length ? [...core, { id: 'otherPreferences', key: 'companions', label: '其他偏好', value: `${rest.length} 项`, supplemental: true }] : core
}
