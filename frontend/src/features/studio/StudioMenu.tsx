import { useState } from 'react'
import { Grid2X2, MapPin, Heart, Users, SlidersHorizontal, ArrowLeft } from 'lucide-react'
import { OverlayHost } from './OverlayHost'
import type { ConditionKey } from './types'

const manualConditions: { key: ConditionKey; label: string }[] = [
  { key: 'mainOrigin', label: '出发地' }, { key: 'dates', label: '日期' },
  { key: 'sceneryTypes', label: '想找的地方' }, { key: 'range', label: '目的地范围' },
  { key: 'companions', label: '同行出发地' }, { key: 'weights', label: '推荐偏好' },
]

export function StudioMenu({ onEdit, onNew, onFavorites, onTeam }: { onEdit: (key: ConditionKey) => void; onNew: () => void; onClear: () => void; onFavorites?: () => void; onTeam?: () => void }) {
  const [open, setOpen] = useState(false)
  const [manual, setManual] = useState(false)
  return <div className='studio-tools'><button type='button' aria-expanded={open} aria-label='更多功能' title='更多功能' onClick={() => { setManual(false); setOpen(!open) }}><Grid2X2 size={20} /></button>
    {open && <OverlayHost label={manual ? '填写条件' : '更多功能'} onClose={() => setOpen(false)} panelClassName='studio-feature-library glass-panel'>
      {manual ? <>
        <button type='button' className='text-button' onClick={() => setManual(false)}><ArrowLeft size={18} />返回</button>
        {manualConditions.map(({ key, label }) => <button key={key} type='button' onClick={() => { setOpen(false); onEdit(key) }}>{label}</button>)}
      </> : <>
      <button type='button' onClick={() => setManual(true)}><SlidersHorizontal size={22} /><span>手动填写条件</span></button>
      <button type='button' onClick={() => { setOpen(false); onEdit('targetPlace') }}><MapPin size={22} /><span>评估指定地点</span></button>
      <button type='button' onClick={() => { setOpen(false); onFavorites?.() }}><Heart size={22} /><span>从收藏中选择</span></button>
      <button type='button' onClick={() => { setOpen(false); onTeam?.() }}><Users size={22} /><span>发起同行挑选</span></button>
      <button type='button' className='text-button' onClick={() => { setOpen(false); onNew() }}>重新开始</button>
      </>}
    </OverlayHost>}
  </div>
}
