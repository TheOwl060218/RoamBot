import { RotateCcw } from 'lucide-react'

import type { DisplayWeights } from './formState'

type WeightKey = keyof DisplayWeights
const labels: Record<WeightKey, string> = {
  weather: '天气适配',
  distance: '距离远近',
  popularity: '景区热度',
}

type WeightSegmentsProps = {
  value: DisplayWeights
  onChange: (value: DisplayWeights) => void
  onReset: () => void
}

export function WeightSegments({ value, onChange, onReset }: WeightSegmentsProps) {
  const active: WeightKey[] = ['weather', 'distance', 'popularity']

  function update(key: WeightKey, requested: number) {
    const index = active.indexOf(key)
    const partner = active[index < active.length - 1 ? index + 1 : index - 1]
    const pairTotal = value[key] + value[partner]
    const nextValue = Math.min(pairTotal, Math.max(0, Math.round(requested / 5) * 5))
    onChange({ ...value, [key]: nextValue, [partner]: pairTotal - nextValue })
  }

  return (
    <fieldset className="form-section weights-section">
      <legend>推荐权重</legend>
      <div className="weight-summary" aria-label="权重分配">
        {active.map((key) => (
          <span key={key} style={{ flexGrow: Math.max(value[key], 5) }}>
            {labels[key]} {value[key]}%
          </span>
        ))}
      </div>
      <div className="weight-controls">
        {active.map((key) => (
          <label className="range-field" key={key}>
            <span>{labels[key]}</span>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={value[key]}
              aria-label={`${labels[key]}权重`}
              onChange={(event) => update(key, Number(event.target.value))}
            />
            <output>{value[key]}%</output>
          </label>
        ))}
      </div>
      <button className="icon-text-button" type="button" onClick={onReset}>
        <RotateCcw aria-hidden="true" size={16} />
        恢复默认
      </button>
    </fieldset>
  )
}
