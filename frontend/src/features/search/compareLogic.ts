import type { RecommendationItem } from '../../api/types'

export type ComparisonMetricKey =
  | 'total'
  | 'weather'
  | 'avgDistance'
  | 'maxDistance'
  | 'distance'
  | 'fairness'
  | 'popularity'

export type ComparedValue = {
  providerId: string
  name: string
  value: number | null
}

export type ComparisonRow = {
  key: ComparisonMetricKey
  label: string
  values: ComparedValue[]
  bestIds: string[]
}

export type ComparisonResult = {
  rows: ComparisonRow[]
  conclusions: string[]
}

const TOTAL_LEAD = 10
const TOTAL_CLOSE = 5
const WEATHER_LEAD = 15
const FAIRNESS_LEAD = 20

type MetricInput = {
  label: string
  value: (item: RecommendationItem) => number | null
  direction: 'max' | 'min'
}

const METRICS: Record<ComparisonMetricKey, MetricInput> = {
  total: { label: '综合分', value: (item) => item.score.total, direction: 'max' },
  weather: { label: '天气适宜度', value: (item) => item.score.weather, direction: 'max' },
  avgDistance: {
    label: '平均路程',
    value: (item) => item.group_accessibility.average_distance_km,
    direction: 'min',
  },
  maxDistance: {
    label: '最大路程',
    value: (item) => item.group_accessibility.max_distance_km,
    direction: 'min',
  },
  distance: { label: '路程评分', value: (item) => item.score.distance, direction: 'max' },
  fairness: {
    label: '多人公平性',
    value: (item) => item.group_accessibility.fairness_score,
    direction: 'max',
  },
  popularity: { label: '地点热度', value: (item) => item.score.popularity, direction: 'max' },
}

function bestIdsFor(values: ComparedValue[], direction: 'max' | 'min'): string[] {
  const present = values.filter((v) => v.value !== null)
  if (present.length === 0) return []
  const best = direction === 'max'
    ? Math.max(...present.map((v) => v.value as number))
    : Math.min(...present.map((v) => v.value as number))
  return present.filter((v) => v.value === best).map((v) => v.providerId)
}

function leadGap(values: ComparedValue[]): number {
  if (values.length < 2) return 0
  const sorted = [...values].sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
  return (sorted[0].value ?? 0) - (sorted[1].value ?? 0)
}

export function compareCandidates(
  items: RecommendationItem[],
  originCount: number,
): ComparisonResult | null {
  if (items.length < 2) return null

  const rows: ComparisonRow[] = (Object.keys(METRICS) as ComparisonMetricKey[]).map((key) => {
    const metric = METRICS[key]
    const values: ComparedValue[] = items.map((item) => ({
      providerId: item.destination.provider_id,
      name: item.destination.name,
      value: metric.value(item),
    }))
    return {
      key,
      label: metric.label,
      values,
      bestIds: bestIdsFor(values, metric.direction),
    }
  })

  const nameById = new Map(items.map((item) => [item.destination.provider_id, item.destination.name]))
  const totalRow = rows.find((row) => row.key === 'total')!
  const weatherRow = rows.find((row) => row.key === 'weather')!
  const fairnessRow = rows.find((row) => row.key === 'fairness')!

  const conclusions: string[] = []
  let hasSpecific = false

  if (totalRow.bestIds.length === 1) {
    const [topId] = totalRow.bestIds
    const gap = leadGap(totalRow.values)
    if (gap >= TOTAL_LEAD) {
      conclusions.push(`${nameById.get(topId) ?? ''}综合表现最好，出游匹配指数领先，可作为首选。`)
      hasSpecific = true
    } else if (gap < TOTAL_CLOSE) {
      conclusions.push('候选综合分接近，可根据对天气或距离的偏好决定。')
      hasSpecific = true
    }
  }

  if (weatherRow.bestIds.length === 1) {
    const [topId] = weatherRow.bestIds
    if (leadGap(weatherRow.values) >= WEATHER_LEAD) {
      conclusions.push(`${nameById.get(topId) ?? ''}天气更适宜，若更看重天气可优先考虑。`)
      hasSpecific = true
    }
  }

  if (originCount >= 2 && fairnessRow.bestIds.length === 1) {
    const [topId] = fairnessRow.bestIds
    if (leadGap(fairnessRow.values) >= FAIRNESS_LEAD) {
      conclusions.push(`${nameById.get(topId) ?? ''}对同行人更公平，多人路程差异更小。`)
      hasSpecific = true
    }
  }

  if (!hasSpecific) {
    conclusions.push(
      originCount >= 2
        ? '候选各有取舍，可结合天气、路程与多人公平性选择。'
        : '候选各有取舍，可结合天气与路程偏好，选择最合适的地点。',
    )
  }

  return { rows, conclusions }
}
