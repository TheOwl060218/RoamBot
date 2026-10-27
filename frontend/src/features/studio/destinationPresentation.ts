import type { RecommendationItem } from '../../api/types'
import { tripMatchIndex, weatherMatchLabel } from '../search/matchLabels'
export function presentDestination(item: RecommendationItem, all: RecommendationItem[]) {
  const others = all.filter(i => i.destination.provider_id !== item.destination.provider_id)
  const advantages: string[] = []
  const tradeoffs: string[] = []
  if (others.length && others.every(i => i.group_accessibility.average_distance_km > item.group_accessibility.average_distance_km)) advantages.push('路程最短')
  if (others.length && others.every(i => i.score.weather < item.score.weather)) advantages.push('天气适配更好')
  if (others.length && item.distances.length > 1 && others.every(i => i.group_accessibility.fairness_score < item.group_accessibility.fairness_score)) advantages.push('同行路程更均衡')
  if (others.some(i => i.group_accessibility.average_distance_km < item.group_accessibility.average_distance_km)) tradeoffs.push('有路程更近的候选')
  if (item.overall_advice !== 'suitable') tradeoffs.push('部分日期需留意天气')
  return { index: tripMatchIndex(item.score.total), weather: weatherMatchLabel(item.score.weather),
    rating: item.destination.rating === null ? '暂无评分' : `${item.destination.rating.toFixed(1)} / 5`, advantages, tradeoffs }
}
