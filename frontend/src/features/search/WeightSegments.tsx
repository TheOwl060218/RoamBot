import { RotateCcw } from 'lucide-react'
import { useRef, type KeyboardEvent, type PointerEvent } from 'react'

import type { DisplayWeights } from './formState'

const STEP = 5

type WeightSegmentsProps = {
  value: DisplayWeights
  onChange: (value: DisplayWeights) => void
  onReset: () => void
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value))
}

function roundToStep(value: number) {
  return Math.round(value / STEP) * STEP
}

export function WeightSegments({ value, onChange, onReset }: WeightSegmentsProps) {
  const barRef = useRef<HTMLDivElement>(null)
  const firstBoundary = value.weather
  const secondBoundary = value.weather + value.distance

  function setBoundary(index: 0 | 1, requested: number) {
    if (index === 0) {
      const next = clamp(roundToStep(requested), 0, secondBoundary)
      onChange({
        weather: next,
        distance: secondBoundary - next,
        popularity: 100 - secondBoundary,
      })
      return
    }

    const next = clamp(roundToStep(requested), firstBoundary, 100)
    onChange({
      weather: firstBoundary,
      distance: next - firstBoundary,
      popularity: 100 - next,
    })
  }

  function pointerValue(event: PointerEvent<HTMLButtonElement>) {
    const bounds = barRef.current?.getBoundingClientRect()
    if (!bounds || bounds.width <= 0) return null
    return ((event.clientX - bounds.left) / bounds.width) * 100
  }

  function startPointer(event: PointerEvent<HTMLButtonElement>, index: 0 | 1) {
    event.currentTarget.setPointerCapture?.(event.pointerId)
    const requested = pointerValue(event)
    if (requested !== null) setBoundary(index, requested)
  }

  function movePointer(event: PointerEvent<HTMLButtonElement>, index: 0 | 1) {
    if (!event.currentTarget.hasPointerCapture?.(event.pointerId)) return
    const requested = pointerValue(event)
    if (requested !== null) setBoundary(index, requested)
  }

  function moveWithKeyboard(event: KeyboardEvent<HTMLButtonElement>, index: 0 | 1) {
    const current = index === 0 ? firstBoundary : secondBoundary
    let requested: number | null = null
    if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') requested = current - STEP
    if (event.key === 'ArrowRight' || event.key === 'ArrowUp') requested = current + STEP
    if (event.key === 'Home') requested = index === 0 ? 0 : firstBoundary
    if (event.key === 'End') requested = index === 0 ? secondBoundary : 100
    if (requested === null) return
    event.preventDefault()
    setBoundary(index, requested)
  }

  return (
    <fieldset className="form-section weights-section">
      <legend>推荐权重</legend>
      <div className="weight-bar" ref={barRef} aria-label="权重比例条">
        <div className="weight-track" aria-hidden="true">
          <span className="weight-segment weight-weather" style={{ width: `${value.weather}%` }} />
          <span className="weight-segment weight-distance" style={{ width: `${value.distance}%` }} />
          <span className="weight-segment weight-popularity" style={{ width: `${value.popularity}%` }} />
        </div>
        <button
          className={`weight-handle weight-handle-first${firstBoundary === secondBoundary ? ' weight-handle-overlap' : ''}`}
          type="button"
          role="slider"
          aria-label="天气与距离分界"
          aria-valuemin={0}
          aria-valuemax={secondBoundary}
          aria-valuenow={firstBoundary}
          aria-valuetext={`天气适配 ${value.weather}%`}
          style={{ left: `${firstBoundary}%` }}
          onKeyDown={(event) => moveWithKeyboard(event, 0)}
          onPointerDown={(event) => startPointer(event, 0)}
          onPointerMove={(event) => movePointer(event, 0)}
        />
        <button
          className={`weight-handle weight-handle-second${firstBoundary === secondBoundary ? ' weight-handle-overlap' : ''}`}
          type="button"
          role="slider"
          aria-label="距离与热度分界"
          aria-valuemin={firstBoundary}
          aria-valuemax={100}
          aria-valuenow={secondBoundary}
          aria-valuetext={`距离远近 ${value.distance}%，景区热度 ${value.popularity}%`}
          style={{ left: `${secondBoundary}%` }}
          onKeyDown={(event) => moveWithKeyboard(event, 1)}
          onPointerDown={(event) => startPointer(event, 1)}
          onPointerMove={(event) => movePointer(event, 1)}
        />
      </div>
      <div className="weight-legend" aria-label="权重分配">
        <span><i className="weight-swatch weight-weather" />天气适配 {value.weather}%</span>
        <span><i className="weight-swatch weight-distance" />距离远近 {value.distance}%</span>
        <span><i className="weight-swatch weight-popularity" />景区热度 {value.popularity}%</span>
      </div>
      <button className="icon-text-button" type="button" onClick={onReset}>
        <RotateCcw aria-hidden="true" size={16} />
        恢复默认
      </button>
    </fieldset>
  )
}
