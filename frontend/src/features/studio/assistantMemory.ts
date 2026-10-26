import type { AssistantConversationState } from './types'

export function emptyConversationState(): AssistantConversationState {
  return { pending_date_request: null }
}

export function readConversationState(value: unknown): AssistantConversationState | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const state = value as Record<string, unknown>
  if (Object.keys(state).some(k => k !== 'pending_date_request')) return null
  const pending = state.pending_date_request
  if (pending === null) return emptyConversationState()
  if (!pending || typeof pending !== 'object' || Array.isArray(pending)) return null
  const fields = pending as Record<string, unknown>
  if (Object.keys(fields).some(k => !['start_date', 'end_date', 'offset_days', 'duration_days'].includes(k))) return null
  for (const k of ['start_date', 'end_date']) {
    const date = fields[k]
    if (date != null && (typeof date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(date)
      || Number.isNaN(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date)) return null
  }
  for (const [k, min, max] of [['offset_days', -366, 366], ['duration_days', 1, 31]] as const) {
    const n = fields[k]
    if (n != null && (typeof n !== 'number' || !Number.isInteger(n) || n < min || n > max)) return null
  }
  if (fields.start_date != null && fields.offset_days != null) return null
  if (!Object.values(fields).some(v => v != null)) return null
  return { pending_date_request: { ...fields } as NonNullable<AssistantConversationState['pending_date_request']> }
}
