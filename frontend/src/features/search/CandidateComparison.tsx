import { useState } from 'react'

import type { RecommendationItem } from '../../api/types'
import { compareCandidates } from './compareLogic'

const MAX_SELECTED = 3

type CandidateComparisonProps = {
  items: RecommendationItem[]
}

function formatValue(value: number | null, withKm: boolean): string {
  if (value === null) return '暂无'
  if (withKm) return `${Math.round(value)} km`
  return String(value)
}

export function CandidateComparison({ items }: CandidateComparisonProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  if (items.length < 2) return null

  const selectedItems = items.filter((item) => selectedIds.includes(item.destination.provider_id))
  const originCount = selectedItems[0]?.distances.length ?? 1
  const result = selectedItems.length >= 2 ? compareCandidates(selectedItems, originCount) : null

  function toggle(id: string) {
    setSelectedIds((current) => {
      if (current.includes(id)) return current.filter((value) => value !== id)
      if (current.length >= MAX_SELECTED) return current
      return [...current, id]
    })
  }

  return (
    <fieldset className="candidate-comparison">
      <legend>选择候选进行对比</legend>
      <div className="comparison-selector">
        {items.map((item) => {
          const id = item.destination.provider_id
          const selected = selectedIds.includes(id)
          const disabled = !selected && selectedIds.length >= MAX_SELECTED
          return (
            <label key={id} className="comparison-option">
              <input
                type="checkbox"
                checked={selected}
                disabled={disabled}
                onChange={() => toggle(id)}
              />
              <span>{item.destination.name}</span>
            </label>
          )
        })}
        {selectedIds.length >= MAX_SELECTED && (
          <span className="comparison-hint">最多同时比较三个候选</span>
        )}
      </div>

      {result && (
        <>
          <div className="comparison-table-scroll">
            <table className="candidate-comparison-table">
              <caption>候选地点对比</caption>
              <thead>
                <tr>
                  <th scope="col" />
                  {selectedItems.map((item) => (
                    <th key={item.destination.provider_id} scope="col">
                      {item.destination.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => {
                  const withKm = row.key === 'avgDistance' || row.key === 'maxDistance'
                  return (
                    <tr key={row.key}>
                      <th scope="row">{row.label}</th>
                      {row.values.map((compared) => (
                        <td key={compared.providerId}>
                          <span className="comparison-value">
                            {formatValue(compared.value, withKm)}
                          </span>
                          {row.bestIds.includes(compared.providerId) && (
                            <span className="comparison-best">最佳</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {result.conclusions.map((conclusion) => (
            <p key={conclusion} className="comparison-conclusion">
              {conclusion}
            </p>
          ))}
        </>
      )}
    </fieldset>
  )
}
