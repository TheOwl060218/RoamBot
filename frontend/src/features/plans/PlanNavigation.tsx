import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { CalendarDays } from 'lucide-react'

import { apiClient } from '../../api/client'
import type { TravelPlan } from '../../api/types'
import { useAuth } from '../auth/authContext'
import { PLAN_CHANGED_EVENT, compactDates, planProgress } from './planPresentation'
import { usePlanClock } from './usePlanClock'

export function PlanNavigation({ mobile = false }: { mobile?: boolean }) {
  const { user } = useAuth()
  const location = useLocation()
  const [ownedPlans, setOwnedPlans] = useState<{ username: string; plans: TravelPlan[] } | null>(null)
  const [expanded, setExpanded] = useState(false)
  const previousId = useRef<string | null>(null)
  const now = usePlanClock()
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(now))

  useEffect(() => {
    if (!user) return
    let live = true
    const load = () => void apiClient.get<{ plans: TravelPlan[] }>('/plans').then(response => {
      if (live) setOwnedPlans({ username: user.username, plans: response.plans })
    }).catch(() => undefined)
    load()
    window.addEventListener(PLAN_CHANGED_EVENT, load)
    window.addEventListener('focus', load)
    const timer = window.setInterval(load, 60000)
    return () => { live = false; window.clearInterval(timer); window.removeEventListener(PLAN_CHANGED_EVENT, load); window.removeEventListener('focus', load) }
  }, [user, location.pathname])

  const active = (user && ownedPlans?.username === user.username ? ownedPlans.plans ?? [] : [])
    .filter(p => !p.ended && p.end_date >= today)
    .sort((a, b) => a.start_date.localeCompare(b.start_date) || a.created_at.localeCompare(b.created_at))[0]
  const activeId = active?.id
  useEffect(() => {
    if (!activeId || activeId === previousId.current) return
    previousId.current = activeId
    const begin = window.setTimeout(() => setExpanded(true), 0)
    const end = window.setTimeout(() => setExpanded(false), 4000)
    return () => { window.clearTimeout(begin); window.clearTimeout(end) }
  }, [activeId])

  if (!active) return mobile ? null : <NavLink className={({ isActive }) => `nav-link plan-nav-plain${isActive ? ' active' : ''}`} to='/plans'>计划中心</NavLink>
  const label = `${active.city} ${compactDates(active.start_date, active.end_date)}`
  const state = active.status === 'decided' ? `已决定 ${active.candidates.find(c => c.id === active.final_candidate_id)?.snapshot.destination.name ?? ''}` : `${active.status === 'closed' ? '待决定' : '投票中'} ${planProgress(active)}`
  return <div className={mobile ? 'mobile-plan-anchor' : 'plan-nav-anchor'}>
    <NavLink to={`/plans/${active.id}`} className={`plan-status-link${expanded ? ' expanded' : ''}`}
      aria-label={`计划中心：${label}，${state}`} title={`${label} ${state}`}>
      <CalendarDays size={16} aria-hidden='true' /><span className='plan-status-title'>{label}</span><span className='plan-status-detail'>{state}</span>
    </NavLink>
  </div>
}
