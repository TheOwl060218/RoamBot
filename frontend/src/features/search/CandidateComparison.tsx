import type { RecommendationItem } from '../../api/types'
import { compareCandidates } from './compareLogic'
import { useCandidateComparison } from './useCandidateComparison'

const MAX_SELECTED = 3

type CandidateComparisonProps = {
  items: RecommendationItem[]
  onViewComparison?: () => void
}

function formatValue(value: number | null, withKm: boolean): string {
  if (value === null) return '暂无'
  if (withKm) return `${Math.round(value)} km`
  return String(value)
}

export function CandidateComparisonSelector({
  items,
  selectedIds,
  toggle,
  onViewComparison,
}: {
  items: RecommendationItem[]
  selectedIds: string[]
  toggle: (id: string) => void
  onViewComparison?: () => void
}) {
  return (
    <fieldset className="candidate-comparison candidate-comparison-selector">
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
      <div className="comparison-next-step" aria-live="polite">
        {selectedIds.length === 0 && (
          <p>选择 2～3 个候选，比较天气、路程与多人公平性。</p>
        )}
        {selectedIds.length === 1 && (
          <p>已选择 1 个，再选 1 个即可生成对比。</p>
        )}
        {selectedIds.length >= 2 && onViewComparison && (
          <button className="comparison-view-button" type="button" onClick={onViewComparison}>
            查看对比结果（{selectedIds.length}）
            <span aria-hidden="true">→</span>
          </button>
        )}
        {selectedIds.length >= 2 && !onViewComparison && (
          <p>已生成 {selectedIds.length} 个候选的对比结果。</p>
        )}
      </div>
    </fieldset>
  )
}

export function CandidateComparisonTable({
  selectedItems,
  result,
}: {
  selectedItems: RecommendationItem[]
  result: NonNullable<ReturnType<typeof compareCandidates>>
}) {
  return (
    <div className="candidate-comparison-table-wrap">
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
    </div>
  )
}

export function CandidateComparison({ items, onViewComparison }: CandidateComparisonProps) {
  const state = useCandidateComparison(items)
  if (!state.canCompare) return null
  const { result, selectedItems } = state
  return (
    <div className="candidate-comparison-host">
      <CandidateComparisonSelector
        items={state.items}
        selectedIds={state.selectedIds}
        toggle={state.toggle}
        onViewComparison={onViewComparison}
      />
      {result && selectedItems && (
        <CandidateComparisonTable selectedItems={selectedItems} result={result} />
      )}
    </div>
  )
}
