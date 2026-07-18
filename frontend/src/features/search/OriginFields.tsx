import { Minus, Plus } from 'lucide-react'

type OriginFieldsProps = {
  mainOrigin: string
  companions: string[]
  errors: Record<string, string>
  onMainChange: (value: string) => void
  onCompanionsChange: (value: string[]) => void
}

export function OriginFields({
  mainOrigin,
  companions,
  errors,
  onMainChange,
  onCompanionsChange,
}: OriginFieldsProps) {
  return (
    <fieldset className="form-section">
      <legend>从哪里出发</legend>
      <label className="field">
        <span>主出发地</span>
        <input
          value={mainOrigin}
          onChange={(event) => onMainChange(event.target.value)}
          placeholder="例如：苏州站"
        />
        {errors.main_origin && <small className="field-error">{errors.main_origin}</small>}
      </label>

      {companions.map((origin, index) => (
        <div className="companion-row" key={index}>
          <label className="field">
            <span>{`同行人 ${index + 1} 出发地`}</span>
            <input
              value={origin}
              onChange={(event) => {
                const next = [...companions]
                next[index] = event.target.value
                onCompanionsChange(next)
              }}
              placeholder="输入同行人的出发地"
            />
            {errors[`companion_origins[${index}]`] && (
              <small className="field-error">{errors[`companion_origins[${index}]`]}</small>
            )}
          </label>
          <button
            className="icon-button"
            type="button"
            aria-label={`删除同行人 ${index + 1}`}
            onClick={() => onCompanionsChange(companions.filter((_, itemIndex) => itemIndex !== index))}
          >
            <Minus aria-hidden="true" size={18} />
          </button>
        </div>
      ))}

      {companions.length < 2 && (
        <button
          className="text-button"
          type="button"
          onClick={() => onCompanionsChange([...companions, ''])}
        >
          <Plus aria-hidden="true" size={17} />
          添加同行人
        </button>
      )}
    </fieldset>
  )
}
