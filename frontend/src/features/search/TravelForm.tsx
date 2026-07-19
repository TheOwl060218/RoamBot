import { useState, type FormEvent } from 'react'

import type {
  PlaceEvaluationRequest,
  RankingWeights,
  RecommendationRequest,
  SceneryType,
  SearchMode,
} from '../../api/types'
import {
  chinaDate,
  groupWeights,
  loadWeightPreference,
  saveWeightPreference,
  singleWeights,
} from './formState'
import { OriginFields } from './OriginFields'
import { ScenerySelector } from './ScenerySelector'
import { WeightSegments } from './WeightSegments'

type TravelFormProps = {
  initialMode?: SearchMode
  initialTarget?: string
  isSubmitting?: boolean
  fieldErrors?: Record<string, string>
  onSubmit: (request: RecommendationRequest | PlaceEvaluationRequest) => void | Promise<void>
}

export function TravelForm({
  initialMode = 'recommendation',
  initialTarget = '',
  isSubmitting = false,
  fieldErrors = {},
  onSubmit,
}: TravelFormProps) {
  const [mode, setMode] = useState<SearchMode>(initialMode)
  const [city, setCity] = useState('苏州')
  const [mainOrigin, setMainOrigin] = useState('')
  const [companions, setCompanions] = useState<string[]>([])
  const [maxDistance, setMaxDistance] = useState('50')
  const [startDate, setStartDate] = useState(chinaDate(1))
  const [endDate, setEndDate] = useState(chinaDate(1))
  const [sceneryTypes, setSceneryTypes] = useState<SceneryType[]>([])
  const [matchMode, setMatchMode] = useState<'any' | 'cover_all'>('any')
  const [targetPlace, setTargetPlace] = useState(initialTarget)
  const [weights, setWeights] = useState<RankingWeights>(
    () => loadWeightPreference(initialMode, 1) ?? singleWeights,
  )
  const [localErrors, setLocalErrors] = useState<Record<string, string>>({})
  const errors = { ...localErrors, ...fieldErrors }
  const originCount = (companions.length + 1) as 1 | 2 | 3
  const maxDistanceKm = Number(maxDistance)

  function changeCompanions(next: string[]) {
    const switchesGroupMode = (companions.length === 0) !== (next.length === 0)
    setCompanions(next)
    if (switchesGroupMode) {
      const nextCount = (next.length + 1) as 1 | 2 | 3
      setWeights(loadWeightPreference(mode, nextCount) ?? (next.length === 0 ? singleWeights : groupWeights))
    }
  }

  function changeMode(nextMode: SearchMode) {
    setMode(nextMode)
    setWeights(loadWeightPreference(nextMode, originCount) ?? (originCount === 1 ? singleWeights : groupWeights))
  }

  function changeWeights(next: RankingWeights) {
    setWeights(next)
    saveWeightPreference(mode, originCount, next)
  }

  function resetWeights() {
    const next = originCount === 1 ? singleWeights : groupWeights
    setWeights(next)
    saveWeightPreference(mode, originCount, next)
  }

  function validate() {
    const next: Record<string, string> = {}
    if (!mainOrigin.trim()) next.main_origin = '请输入主出发地'
    companions.forEach((origin, index) => {
      if (!origin.trim()) next[`companion_origins[${index}]`] = '请输入同行人出发地'
    })
    if (maxDistance === '' || maxDistanceKm <= 0 || maxDistanceKm > 500) {
      next.max_distance_km = '最大距离必须在 0 到 500 km 之间'
    }
    if (startDate < chinaDate(0) || endDate > chinaDate(6)) {
      next.start_date = '日期必须在今天至未来第 6 天内'
    }
    if (endDate < startDate) next.end_date = '结束日期不能早于开始日期'
    if (mode === 'recommendation' && sceneryTypes.length === 0) {
      next.scenery_types = '请至少选择一种风景类型'
    }
    if (mode === 'place_evaluation' && !targetPlace.trim()) {
      next.target_place = '请输入目标地点'
    }
    setLocalErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!validate()) return
    const common = {
      city: city.trim() || '苏州',
      main_origin: mainOrigin.trim(),
      companion_origins: companions.map((origin) => origin.trim()),
      max_distance_km: maxDistanceKm,
      start_date: startDate,
      end_date: endDate,
      weights,
    }
    if (mode === 'recommendation') {
      await onSubmit({ ...common, scenery_types: sceneryTypes, scenery_match_mode: matchMode })
    } else {
      await onSubmit({ ...common, target_place: targetPlace.trim() })
    }
  }

  return (
    <form className="travel-form" onSubmit={handleSubmit} noValidate>
      <div className="form-heading">
        <div>
          <p className="eyebrow">天气感知的风景出行推荐</p>
          <h1>想去哪里走走？</h1>
        </div>
        <div className="mode-switch" role="radiogroup" aria-label="查询模式">
          <label>
            <input
              type="radio"
              name="mode"
              checked={mode === 'recommendation'}
              onChange={() => changeMode('recommendation')}
            />
            <span>推荐地点</span>
          </label>
          <label>
            <input
              type="radio"
              name="mode"
              checked={mode === 'place_evaluation'}
              onChange={() => changeMode('place_evaluation')}
            />
            <span>评估指定地点</span>
          </label>
        </div>
      </div>

      <div className="form-grid">
        <label className="field">
          <span>城市</span>
          <input value={city} onChange={(event) => setCity(event.target.value)} />
        </label>
        <label className="field">
          <span>最大距离（km）</span>
          <input
            type="number"
            min="1"
            max="500"
            value={maxDistance}
            onChange={(event) => setMaxDistance(event.target.value.replace(/^0+(?=\d)/, ''))}
          />
          {errors.max_distance_km && <small className="field-error">{errors.max_distance_km}</small>}
        </label>
        <label className="field">
          <span>开始日期</span>
          <input
            type="date"
            min={chinaDate(0)}
            max={chinaDate(6)}
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
          {errors.start_date && <small className="field-error">{errors.start_date}</small>}
        </label>
        <label className="field">
          <span>结束日期</span>
          <input
            type="date"
            min={startDate}
            max={chinaDate(6)}
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
          {errors.end_date && <small className="field-error">{errors.end_date}</small>}
        </label>
      </div>

      <OriginFields
        mainOrigin={mainOrigin}
        companions={companions}
        errors={errors}
        onMainChange={setMainOrigin}
        onCompanionsChange={changeCompanions}
      />

      {mode === 'recommendation' ? (
        <>
          <ScenerySelector value={sceneryTypes} error={errors.scenery_types} onChange={setSceneryTypes} />
          <fieldset className="form-section compact-section">
            <legend>偏好匹配</legend>
            <label className="inline-choice">
              <input
                type="radio"
                name="match-mode"
                checked={matchMode === 'any'}
                onChange={() => setMatchMode('any')}
              />
              匹配任意一种
            </label>
            <label className="inline-choice">
              <input
                type="radio"
                name="match-mode"
                checked={matchMode === 'cover_all'}
                onChange={() => setMatchMode('cover_all')}
              />
              尽量覆盖全部
            </label>
          </fieldset>
        </>
      ) : (
        <label className="field target-field">
          <span>目标地点</span>
          <input
            value={targetPlace}
            onChange={(event) => setTargetPlace(event.target.value)}
            placeholder="例如：金鸡湖"
          />
          {errors.target_place && <small className="field-error">{errors.target_place}</small>}
        </label>
      )}

      <WeightSegments
        originCount={originCount}
        value={weights}
        onChange={changeWeights}
        onReset={resetWeights}
      />

      <button className="primary-button submit-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? '正在计算…' : mode === 'recommendation' ? '开始推荐' : '评估这个地点'}
      </button>
    </form>
  )
}
