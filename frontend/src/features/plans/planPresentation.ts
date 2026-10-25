import { ApiError } from '../../api/client'
import type { TravelPlan } from '../../api/types'

export const PLAN_CHANGED_EVENT = 'roambot.plan-changed'
export function announcePlanChange() {
  window.dispatchEvent(new Event(PLAN_CHANGED_EVENT))
}

export function compactDates(start: string, end: string, year = new Date().getFullYear()) {
  const format = (value: string) => (Number(value.slice(0, 4)) === year ? value.slice(5) : value.slice(2)).replaceAll('-', '.')
  return `${format(start)}${start === end ? '' : `–${format(end)}`}`
}

export function defaultPlanName(city: string, start: string, end: string) {
  return `${city} ${compactDates(start, end)} 出行计划`
}

export function planProgress(plan: TravelPlan) {
  const count = plan.summary?.voted_count ?? 0
  return count > plan.expected_count ? `${count} 人已参与` : `${count}/${plan.expected_count} 人已投票`
}

export function planStatus(plan: TravelPlan) {
  return plan.ended ? '已结束' : plan.status === 'closed' ? '待决定' : plan.status === 'decided' ? '已决定' : '投票中'
}

export function planError(error: unknown) {
  const messages: Record<string, string> = {
    plan_not_found: '计划不存在，或当前账户没有访问权限。',
    plan_dates_required: '请选择出行日期。',
    plan_dates_invalid: '出行日期请选在未来七天内。',
    history_not_eligible: '请先确认使用原条件重新推荐。',
    candidate_not_in_history: '候选已变化，请重新选择候选。',
    nickname_taken: '这个昵称已有人使用，请换一个。',
    invite_expired: '邀请已过期，请联系发起者。',
    invite_revoked: '邀请已撤销，请向发起者索取新链接。',
    vote_closed: '投票已结束，暂时不能投票或改票。',
    plan_ended: '出行日期已结束，不能再修改投票或目的地。',
    participant_required: '请先加入计划；身份被移除后需重新加入。',
    anonymous_csrf_invalid: '会话已刷新，请重新加载页面后再投票。',
    weather_check_cooldown: '一小时内无需重复检查，请等待下一次可检查时间。',
    invalid_plan_transition: '当前计划状态不支持该操作。',
    provider_unavailable: '天气服务暂时不可用，已保留上次有效结果。',
    validation_error: '请检查名称、昵称或人数是否符合要求。',
  }
  return error instanceof ApiError ? messages[error.code] ?? error.message : '操作失败，请稍后重试。'
}
