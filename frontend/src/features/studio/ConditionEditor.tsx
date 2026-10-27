import { useId, useState, type ReactNode } from 'react'
import { OverlayHost } from './OverlayHost'
import type { TravelFormDraft } from '../search/formState'
import { defaultDisplayWeights } from '../search/formState'
import { RegionInput } from '../search/RegionInput'
import { StudioDatePicker } from './StudioDatePicker'
import { WeightSegments } from '../search/WeightSegments'
import type { ConditionKey } from './types'
import { conditionLabels } from './conditionLabels'
import { StudioPlaceField } from './StudioPlaceField'
import { localSceneryTypes } from './localScenery'

export function ConditionEditor({ conditionKey, draft, onSave, onClose, accessory }: {
  conditionKey: ConditionKey; draft: TravelFormDraft; onSave: (draft: TravelFormDraft) => void; onClose: () => void
  accessory?: ReactNode
}) {
  // Opening evaluation is a local edit; only Save commits its mode change.
  const [value, setValue] = useState(() => conditionKey === 'targetPlace'
    ? { ...draft, mode: 'place_evaluation' as const } : draft)
  const [query, setQuery] = useState('')
  const heading = useId()
  function update(part: Partial<TravelFormDraft>) { setValue(v => ({ ...v, ...part })) }
  return <OverlayHost label={conditionLabels[conditionKey]} onClose={onClose} className='studio-editor-backdrop' panelClassName='studio-editor glass-panel' accessory={accessory}>
    <header><h2 id={heading}>{conditionLabels[conditionKey]}</h2><button type='button' onClick={onClose} aria-label='关闭条件编辑'>×</button></header>
    <form noValidate onSubmit={e => { e.preventDefault(); onSave(conditionKey === 'sceneryTypes' ? { ...value, sceneryTypes: localSceneryTypes(value.sceneryQuery ?? '') } : value) }}>
      {conditionKey === 'mainOrigin' && <StudioPlaceField label='主出发地' city='' value={value.mainOrigin} onChange={mainOrigin => update({ mainOrigin, mainOriginCoordinate: null })} onSelect={s => update({ mainOrigin: s.name, mainOriginCoordinate: s.coordinate })} />}
      {conditionKey === 'companions' && <div className='studio-field-stack'>
        {value.companions.map((name, i) => <div key={i}><StudioPlaceField label={`同行人 ${i + 1} 出发地`} city='' value={name} onChange={text => update({ companions: value.companions.map((v,j) => j === i ? text : v), companionOriginCoordinates: value.companions.map((_,j) => j === i ? null : value.companionOriginCoordinates[j] ?? null) })} onSelect={s => update({ companions: value.companions.map((v,j) => j === i ? s.name : v), companionOriginCoordinates: value.companions.map((_,j) => j === i ? s.coordinate : value.companionOriginCoordinates[j] ?? null) })} /><button type='button' onClick={() => update({ companions: value.companions.filter((_,j) => j !== i), companionOriginCoordinates: value.companionOriginCoordinates.filter((_,j) => j !== i) })}>移除此出发地</button></div>)}
        <button type='button' disabled={value.companions.length >= 2} onClick={() => update({ companions: [...value.companions, ''], companionOriginCoordinates: [...value.companionOriginCoordinates, null] })}>添加同行出发地</button>
      </div>}
      {conditionKey === 'dates' && <StudioDatePicker start={value.startDate} end={value.endDate} onChange={(startDate, endDate) => update({ startDate, endDate })} />}
      {conditionKey === 'sceneryTypes' && <label className='field'><span>想找什么样的地方</span><textarea autoFocus rows={3} maxLength={120} placeholder='比如：安静的水边，适合散步' value={value.sceneryQuery ?? ''} onChange={e => update({ sceneryQuery: e.target.value, sceneryTypes: [], sceneryKeywords: [] })} /></label>}
      {conditionKey === 'range' && <div className='studio-field-stack'><label className='field'><span>最大距离（km）</span><input type='number' inputMode='decimal' min={1} max={500} disabled={!!value.destinationRegions?.length} value={value.maxDistance} onChange={e => update({ maxDistance: e.target.value.replace(/^0+(?=\d)/, '') })} /></label><div className='field'><span>目的地城市范围</span><RegionInput value={value.destinationRegions ?? []} onChange={destinationRegions => update({ destinationRegions })} query={query} onQueryChange={setQuery} /></div>{!!value.destinationRegions?.length && <p>已按目的地范围筛选，距离不再作为限制。</p>}</div>}
      {conditionKey === 'targetPlace' && <><label className='field'><span>查询方式</span><select value={value.mode} onChange={e => update({ mode: e.target.value as TravelFormDraft['mode'] })}><option value='recommendation'>推荐地点</option><option value='place_evaluation'>评估指定地点</option></select></label>{value.mode === 'place_evaluation' && <StudioPlaceField label='目标地点' city='' value={value.targetPlace} onChange={targetPlace => update({ targetPlace })} onSelect={place => update({ targetPlace: place.name })} />}</>}
      {conditionKey === 'weights' && <WeightSegments value={value.weights ?? defaultDisplayWeights} onChange={weights => update({ weights })} onReset={() => update({ weights: undefined })} />}
      <footer><button type='submit' className='primary-button'>保存条件</button></footer>
    </form>
  </OverlayHost>
}
