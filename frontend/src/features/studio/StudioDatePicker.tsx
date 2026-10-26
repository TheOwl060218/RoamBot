import { useState } from 'react'
import { chinaDate } from '../search/formState'

function addDays(date: string, offset: number) {
  const day = new Date(`${date}T12:00:00Z`)
  day.setUTCDate(day.getUTCDate() + offset)
  return day.toISOString().slice(0, 10)
}
export function StudioDatePicker({ start, end, onChange, today = chinaDate(0) }: {
  start: string; end: string; onChange: (start: string, end: string) => void; today?: string
}) {
  const [custom, setCustom] = useState(false)
  const [anchor, setAnchor] = useState<string | null>(null)
  const days = Array.from({ length: 7 }, (_, i) => addDays(today, i))
  const weekday = new Date(`${today}T12:00:00Z`).getUTCDay()
  const saturday = weekday === 0 ? -1 : 6 - weekday
  const weekendStart = addDays(today, Math.max(0, saturday))
  const weekendEnd = addDays(today, saturday + 1)
  function quick(a: string, b: string) { setAnchor(null); onChange(a, b) }
  return <div className='studio-date-picker'>
    <div className='studio-date-shortcuts'>
      <button type='button' onClick={() => quick(today, today)}>今天</button>
      <button type='button' onClick={() => quick(days[1], days[1])}>明天</button>
      <button type='button' onClick={() => quick(weekendStart, weekendEnd)}>这周末</button>
      <button type='button' disabled={addDays(today, saturday + 8) > days[6]} onClick={() => quick(addDays(today, saturday + 7), addDays(today, saturday + 8))}>下周末</button>
      <button type='button' aria-pressed={custom} onClick={() => setCustom(!custom)}>自选日期</button>
    </div>
    <p className='studio-date-summary'>{start ? `${start} ${end && end !== start ? `— ${end}` : ''}` : '选择想出发的时间'}</p>
    {custom && <div className='studio-date-days' aria-label='未来七天'>
      {days.map(date => <button type='button' key={date} aria-label={date} aria-pressed={!!start && date >= start && date <= end}
        onClick={() => {
          if (!anchor) { setAnchor(date); onChange(date, date) }
          else { onChange(anchor < date ? anchor : date, anchor < date ? date : anchor); setAnchor(null) }
        }}><small>{['周日','周一','周二','周三','周四','周五','周六'][new Date(`${date}T12:00:00Z`).getUTCDay()]}</small><strong>{Number(date.slice(8))}</strong></button>)}
    </div>}
    {custom && <small>先点开始日期，再点结束日期 · 未来七天</small>}
  </div>
}
