import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import type { PlanCandidate, TravelPlan } from '../../api/types'
import { DailyWeatherList } from '../search/DailyWeatherList'
import { RevealNotice } from '../../components/RevealNotice'
import { useRevealNotice } from '../../components/useRevealNotice'
import { DayExplanationPopover } from './DayExplanationPopover'
import { useCommandTarget } from '../commands/commandContext'

type Props = { plan: TravelPlan; hideHeading?: boolean; decisionAction?: (candidate: PlanCandidate) => ReactNode; toolbarActions?: ReactNode }
const sources: Record<string, string> = { demo: '演示数据', cache: '缓存数据', live: '实时数据' }
function datesBetween(start: string, end: string) {
  const dates: string[] = []
  const date = new Date(`${start}T00:00:00Z`), last = Date.parse(`${end}T00:00:00Z`)
  while (Number.isFinite(date.getTime()) && date.getTime() <= last) {
    dates.push(date.toISOString().slice(0, 10))
    date.setUTCDate(date.getUTCDate() + 1)
  }
  return dates
}
function shortDate(date: string) { const [, month, day] = date.split('-'); return `${Number(month)}.${Number(day)}` }
function weatherData(candidate: PlanCandidate) {
  const check = candidate.latest_weather
  return { weather: check ? check.weather ?? [] : candidate.snapshot.weather, suitability: check ? check.daily_suitability ?? [] : 'schema_version' in candidate.snapshot ? [] : candidate.snapshot.daily_suitability ?? [] }
}

export function PlanComparison(props: Props) { return <ComparisonBody key={props.plan.id} {...props} /> }
function ComparisonBody({ plan, hideHeading, decisionAction, toolbarActions }: Props) {
  const dates = datesBetween(plan.start_date, plan.end_date)
  const [selectedDate, setSelectedDate] = useState(plan.start_date)
  const currentDate = dates.includes(selectedDate) ? selectedDate : plan.start_date
  const [allDates, setAllDates] = useState(false)
  const [explanationId, setExplanationId] = useState<string | null>(null)
  const closeExplanation = useCallback(() => setExplanationId(null), [])
  const allId = useId()
  const allDatesRef = useRef<HTMLDivElement>(null)
  const { notice, notify, clear } = useRevealNotice()
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      if (allDates) notify(allDatesRef.current, '全部日期已展开，在候选卡片下方查看')
      else clear()
    })
    return () => window.cancelAnimationFrame(frame)
  }, [allDates, notify, clear])
  const candidates = [...plan.candidates].sort((a, b) => Number(b.id === plan.final_candidate_id) - Number(a.id === plan.final_candidate_id))
  useCommandTarget('plan-comparison', () => ({ resource_version: plan.updated_at,
    weather_date: currentDate, all_dates: allDates,
    visible_places: candidates.map(candidate => ({ id: candidate.id, name: candidate.snapshot.destination.name })),
  }), effect => {
    if (effect.tool === 'set_weather_view') {
      const date = String(effect.arguments.date)
      if (date === 'all') setAllDates(true)
      else {
        if (!dates.includes(date)) throw new Error('日期不在当前行程中。')
        setSelectedDate(date); setAllDates(false); closeExplanation()
      }
    } else if (effect.tool === 'show_day_explanation') {
      const id = String(effect.arguments.id)
      if (!candidates.some(c => c.id === id)) throw new Error('候选已变化。')
      setExplanationId(id)
    } else if (effect.tool === 'close_layer' && explanationId) closeExplanation()
    else return false
    return true
  })
  return <section className='plan-comparison' aria-label='候选地点比较'>
    {!hideHeading && <div className='plan-comparison-toolbar'><div><h2>比较候选地点</h2><p className='muted'>同时看同一天，更容易比较差异。</p></div></div>}
    <div className='plan-date-toolbar'>
    <div className='plan-date-tabs' role='group' aria-label='选择比较日期'>{dates.map(date => <button className='icon-text-button' key={date} type='button' aria-pressed={currentDate === date} onClick={() => { closeExplanation(); setSelectedDate(date) }}><time dateTime={date}>{shortDate(date)}</time></button>)}</div>
    <div className='plan-toolbar-actions'><button className='text-button' type='button' aria-expanded={allDates} aria-controls={allId} onClick={() => { if (allDates) clear(); setAllDates(value => !value) }}>{allDates ? '收起全部日期' : '查看全部日期'}</button>{toolbarActions}</div>
    </div>
    <div className='plan-comparison-rail' role='group' aria-label='候选比较卡片' tabIndex={0}>
      <div className={`plan-comparison-cards plan-candidate-count-${candidates.length}`}>{candidates.map(candidate => <ComparisonCard key={candidate.id} candidate={candidate} date={currentDate} final={candidate.id === plan.final_candidate_id} expanded={explanationId === candidate.id} onToggle={() => setExplanationId(id => id === candidate.id ? null : candidate.id)} onClose={closeExplanation}>{decisionAction?.(candidate)}</ComparisonCard>)}</div>
    </div>
    {candidates.length > 1 && <p className='muted plan-rail-hint'>空间不足时，可左右滑动比较候选。</p>}
    {allDates && <div ref={allDatesRef} id={allId} className='plan-all-dates'><table><caption>全部日期天气对比</caption><thead><tr><th scope='col'>日期</th>{candidates.map(c => <th key={c.id} scope='col'>{c.snapshot.destination.name}</th>)}</tr></thead><tbody>{dates.map(date => <tr key={date}><th scope='row'><time dateTime={date}>{shortDate(date)}</time></th>{candidates.map(c => {
      const data = weatherData(c), day = data.weather.find(w => w.date === date), advice = data.suitability.find(w => w.date === date)
      return <td key={c.id}>{day ? <>{day.condition} · {day.temp_min_c}–{day.temp_max_c}°C<br />{advice ? { suitable: '适合前往', caution: '谨慎考虑', not_recommended: '不建议当日前往' }[advice.status] : '暂无判断'}</> : '该日暂无天气记录'}</td>
    })}</tr>)}</tbody></table></div>}
    <RevealNotice notice={notice} />
  </section>
}

function ComparisonCard({ candidate, date, final, children, expanded, onToggle, onClose }: { candidate: PlanCandidate; date: string; final: boolean; children?: ReactNode; expanded: boolean; onToggle: () => void; onClose: () => void }) {
  const trigger = useRef<HTMLButtonElement>(null)
  const detailsId = useId(), item = candidate.snapshot, check = candidate.latest_weather
  const data = weatherData(candidate), weather = data.weather.filter(day => day.date === date)
  const hasExplanation = weather.length > 0 && data.suitability.some(day => day.date === date && Boolean(day.summary?.trim()))
  return <article className={`plan-card plan-comparison-card${final ? ' plan-final' : ''}`}>
    <div className='plan-card-heading'><div className='plan-comparison-title'><h3 title={item.destination.name}>{item.destination.name}</h3>{final && <span className='plan-final-marker'><Check size={14} aria-hidden='true' />最终目的地</span>}</div>{!('schema_version' in item) && <div className='plan-comparison-score'><strong className='plan-score'>{Math.round(item.score.total)}</strong><small>匹配指数</small></div>}</div>
    <p className='muted plan-candidate-address'>{item.destination.address}</p>
    {'schema_version' in item ? <><p className='eyebrow'>{item.experience}</p><p className='discovery-reason'>{item.reason}</p>
      <div className='item-actions'>{item.sources.filter(s => s.url).slice(0, 2).map(s => <a href={s.url} key={s.id} target='_blank' rel='noreferrer'>{s.title || '推荐依据'}</a>)}</div></>
      : <dl className='plan-metrics'><div><dt>平均路程</dt><dd>{item.group_accessibility.average_distance_km.toFixed(1)} km</dd></div><div><dt>最大路程</dt><dd>{item.group_accessibility.max_distance_km.toFixed(1)} km</dd></div><div><dt>多人公平性</dt><dd>{item.group_accessibility.fairness_score.toFixed(0)}</dd></div></dl>}
    {(check || data.weather.length > 0) && <p className='muted plan-weather-source'>{check ? `最近检查 · ${sources[check.source] ?? '服务不可用'}` : `创建时天气 · ${sources['schema_version' in item ? item.source : item.source_state?.kind ?? ''] ?? '来源见原推荐记录'}`}</p>}
    {check && <p className={check.status === 'failed' ? 'field-error' : 'muted'}>{check.status === 'failed' ? '检查失败，保留已有天气记录' : '检查于'} · {new Date(check.checked_at).toLocaleString()}{check.status === 'failed' && check.last_success_at && ` · 上次成功：${new Date(check.last_success_at).toLocaleString()}`}</p>}
    <div className='plan-selected-weather'>
      {weather.length ? <DailyWeatherList weather={weather} suitability={data.suitability.filter(day => day.date === date)} showSummary={false} /> : <p className='plan-missing-weather'>该日暂无天气记录</p>}
    </div>
    <div className='plan-candidate-actions'>{hasExplanation && <button ref={trigger} className='text-button plan-details-toggle' type='button' aria-expanded={expanded} aria-controls={expanded ? detailsId : undefined} aria-haspopup='dialog' aria-label={`${expanded ? '收起' : '查看'}${item.destination.name}详情`} onClick={onToggle}>{expanded ? '收起说明' : '当日说明'}<ChevronDown size={16} aria-hidden='true' /></button>}{children}</div>
    {expanded && hasExplanation && <DayExplanationPopover id={detailsId} title={`${item.destination.name} · ${shortDate(date)} 出行说明`} summary={data.suitability.find(day => day.date === date)!.summary} anchor={trigger} onClose={onClose} />}
  </article>
}
