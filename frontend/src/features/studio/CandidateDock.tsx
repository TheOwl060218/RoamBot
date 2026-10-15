import type { RecommendationItem } from '../../api/types'
import type { ReactNode } from 'react'
export function CandidateDock({ items, onRemove, onCompare, children, hint }: { items: RecommendationItem[]; onRemove: (id: string) => void; onCompare: () => void; children?: ReactNode; hint?: string }) {
  return <aside className='candidate-dock glass-panel' aria-label='已选候选'>
    <div className='candidate-dock-summary'>
      <div><strong>一起选一个目的地</strong><small>选 2–3 个进行比较或邀请同行</small></div>
      <div className='candidate-chips'>{items.map(i => <button type='button' key={i.destination.provider_id} onClick={() => onRemove(i.destination.provider_id)} aria-label={`移出候选：${i.destination.name}`}>{i.destination.name} ×</button>)}</div>
    </div>
    <div className={`candidate-dock-actions${children ? ' with-plan' : ''}`}>
      {children}<button className='text-button' type='button' disabled={items.length < 2} onClick={onCompare}>查看对比（{items.length}）</button>
    </div>
    {hint && <small className='candidate-dock-hint'>{hint}</small>}
  </aside>
}
