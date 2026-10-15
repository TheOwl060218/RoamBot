import { Landmark, Mountain, Trees, Waves } from 'lucide-react'

import type { RecommendationRequest, SceneryType } from '../../api/types'
import { chinaDate, defaultDisplayWeights, loadTravelDraft, toRankingWeights } from './formState'

type SampleScene = {
  id: string
  title: string
  subtitle: string
  Icon: typeof Waves
  sceneryTypes: SceneryType[]
  maxDistance: number
}

const SCENERY_LABELS: Record<SceneryType, string> = {
  lake: '湖景',
  sea: '海景',
  old_town: '古镇',
  museum: '博物馆',
  park: '公园',
  mountain: '山地',
}

const SAMPLE_SCENES: SampleScene[] = [
  {
    id: 'lake',
    title: '湖畔散步',
    subtitle: '选湖景，多留一小时看落日',
    Icon: Waves,
    sceneryTypes: ['lake', 'park'],
    maxDistance: 60,
  },
  {
    id: 'museum',
    title: '博物馆漫游',
    subtitle: '选博物馆，避开日晒慢慢逛',
    Icon: Landmark,
    sceneryTypes: ['museum'],
    maxDistance: 40,
  },
  {
    id: 'mountain',
    title: '山野远足',
    subtitle: '选山地，短途进山呼吸新鲜空气',
    Icon: Mountain,
    sceneryTypes: ['mountain'],
    maxDistance: 70,
  },
  {
    id: 'old-town',
    title: '古镇慢行',
    subtitle: '选古镇，穿过青石板看老建筑',
    Icon: Landmark,
    sceneryTypes: ['old_town'],
    maxDistance: 50,
  },
  {
    id: 'park',
    title: '公园野餐',
    subtitle: '选公园，找片草地晒太阳',
    Icon: Trees,
    sceneryTypes: ['park'],
    maxDistance: 45,
  },
  {
    id: 'lake-museum',
    title: '湖景与博物馆',
    subtitle: '湖边走一圈，再进馆避避晒',
    Icon: Waves,
    sceneryTypes: ['lake', 'museum'],
    maxDistance: 55,
  },
]

const SAMPLE_FILTERS: { id: string; label: string; sceneryTypes: SceneryType[]; maxDistance: number }[] = [
  { id: 'quick', label: '短途近程', sceneryTypes: ['park'], maxDistance: 30 },
  { id: 'rain-day', label: '室内参观', sceneryTypes: ['museum'], maxDistance: 40 },
  { id: 'by-lake', label: '临湖', sceneryTypes: ['lake'], maxDistance: 60 },
  { id: 'old-town', label: '人文古迹', sceneryTypes: ['old_town'], maxDistance: 60 },
]

type SampleScenesProps = {
  onExplore: (request: RecommendationRequest) => void | Promise<void>
  isSubmitting?: boolean
}

function buildRequest(sceneryTypes: SceneryType[], maxDistance: number): RecommendationRequest {
  const date = chinaDate(1)
  const draft = loadTravelDraft()
  const city = draft?.city.trim() || '苏州'
  const companions = draft?.companions.map(origin => origin.trim()) ?? []
  const regions = draft?.destinationRegions ?? []
  const savedDistance = Number(draft?.maxDistance)
  return {
    city: '',
    main_origin: draft?.mainOrigin.trim() || (city === '苏州' ? '苏州站' : ''),
    companion_origins: companions,
    main_origin_coordinate: draft?.mainOriginCoordinate ?? null,
    companion_origin_coordinates: draft?.companionOriginCoordinates ?? [],
    max_distance_km: regions.length ? (savedDistance > 0 && savedDistance <= 500 ? savedDistance : 50) : maxDistance,
    start_date: draft?.startDate ?? date,
    end_date: draft?.endDate ?? date,
    weights: toRankingWeights(draft?.weights ?? defaultDisplayWeights, (companions.length + 1) as 1 | 2 | 3),
    scenery_types: sceneryTypes,
    scenery_match_mode: draft?.matchMode ?? 'any',
    destination_regions: regions,
  }
}

export function SampleScenes({ onExplore, isSubmitting = false }: SampleScenesProps) {
  function runScene(scene: SampleScene) {
    void onExplore(buildRequest(scene.sceneryTypes, scene.maxDistance))
  }
  function runFilter(filter: { id: string; label: string; sceneryTypes: SceneryType[]; maxDistance: number }) {
    void onExplore(buildRequest(filter.sceneryTypes, filter.maxDistance))
  }

  return (
    <section className="sample-scenes" aria-label="示例玩法">
      <div className="sample-scenes-heading">
        <p className="eyebrow">从什么开始？</p>
        <h2>选一种想要的出行方式</h2>
      </div>

      <div className="sample-filter-row" aria-label="快捷玩法">
        {SAMPLE_FILTERS.map((filter) => (
          <button key={filter.id} type="button" disabled={isSubmitting} className="sample-filter-chip" onClick={() => runFilter(filter)}>
            {filter.label}
          </button>
        ))}
      </div>

      <div className="sample-scene-grid">
        {SAMPLE_SCENES.map((scene) => {
          const Icon = scene.Icon
          return (
            <button
              key={scene.id}
              type="button"
              disabled={isSubmitting}
              className="sample-scene-card"
              onClick={() => runScene(scene)}
            >
              <span className="sample-scene-icon"><Icon aria-hidden="true" /></span>
              <span className="sample-scene-text">
                <strong>{scene.title}</strong>
                <small>{scene.subtitle}</small>
                <span className="sample-scene-tags">
                  {scene.sceneryTypes.map((type) => (
                    <span key={type} className="sample-scene-tag">{SCENERY_LABELS[type]}</span>
                  ))}
                  <span className="sample-scene-tag sample-scene-tag-distance">未选省市时 ≤ {scene.maxDistance}km</span>
                </span>
              </span>
            </button>
          )
        })}
      </div>

      <p className="sample-scene-note">
        点击玩法沿用已填写的出发地、日期和目的地范围；未选省市时使用玩法距离。
      </p>
    </section>
  )
}
