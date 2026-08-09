import type { SceneryType } from '../../api/types'

const options: Array<{ value: SceneryType; label: string }> = [
  { value: 'lake', label: '湖景' },
  { value: 'sea', label: '海景' },
  { value: 'old_town', label: '古镇/历史街区' },
  { value: 'museum', label: '博物馆' },
  { value: 'park', label: '公园/绿地/湿地' },
  { value: 'mountain', label: '山地/徒步' },
]

type ScenerySelectorProps = {
  value: SceneryType[]
  error?: string
  onChange: (value: SceneryType[]) => void
}

export function ScenerySelector({ value, error, onChange }: ScenerySelectorProps) {
  return (
    <fieldset className="form-section">
      <legend>风景类型</legend>
      <div className="choice-grid">
        {options.map((option) => (
          <label className="choice" key={option.value}>
            <input
              type="checkbox"
              checked={value.includes(option.value)}
              onChange={(event) => {
                onChange(
                  event.target.checked
                    ? [...value, option.value]
                    : value.filter((item) => item !== option.value),
                )
              }}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
      {error && <small className="field-error">{error}</small>}
    </fieldset>
  )
}
