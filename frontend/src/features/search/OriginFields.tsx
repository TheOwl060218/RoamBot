import { Minus, Plus } from 'lucide-react'
import type { PlaceSuggestion } from '../../api/types'
import { PlaceInput } from './PlaceInput'

type OriginFieldsProps = {
  mainOrigin: string
  city: string
  companions: string[]
  errors: Record<string, string>
  onMainChange: (value: string) => void
  onMainSelect: (suggestion: PlaceSuggestion) => void
  onCompanionChange: (index: number, value: string) => void
  onCompanionSelect: (index: number, suggestion: PlaceSuggestion) => void
  onAddCompanion: () => void
  onRemoveCompanion: (index: number) => void
}

export function OriginFields({
  mainOrigin,
  city,
  companions,
  errors,
  onMainChange,
  onMainSelect,
  onCompanionChange,
  onCompanionSelect,
  onAddCompanion,
  onRemoveCompanion,
}: OriginFieldsProps) {
  return (
    <fieldset className="form-section">
      <legend>从哪里出发</legend>
      <PlaceInput
        label="主出发地"
        value={mainOrigin}
        city={city}
        error={errors.main_origin}
        placeholder="例如：苏州站"
        onChange={onMainChange}
        onSuggestionSelect={onMainSelect}
      />

      {companions.map((origin, index) => (
        <div className="companion-row" key={index}>
          <PlaceInput
            label={`同行人 ${index + 1} 出发地`}
            value={origin}
            city={city}
            error={errors[`companion_origins[${index}]`]}
            placeholder="输入同行人的出发地"
            onChange={(value) => onCompanionChange(index, value)}
            onSuggestionSelect={(suggestion) => onCompanionSelect(index, suggestion)}
          />
          <button
            className="icon-button"
            type="button"
            aria-label={`删除同行人 ${index + 1}`}
            onClick={() => onRemoveCompanion(index)}
          >
            <Minus aria-hidden="true" size={18} />
          </button>
        </div>
      ))}

      {companions.length < 2 && (
        <button
          className="text-button"
          type="button"
          onClick={onAddCompanion}
        >
          <Plus aria-hidden="true" size={17} />
          添加同行人
        </button>
      )}
    </fieldset>
  )
}
