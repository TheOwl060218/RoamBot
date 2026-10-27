import { useEffect, useRef, type Dispatch } from 'react'
import { ApiError } from '../../api/client'
import { requestAccountDialog } from '../../app/accountDialog'
import { requestAssistantTurn } from './assistantClient'
import { toAssistantDraft } from './studioState'
import type { StudioAction, StudioState } from './types'

export function useAssistant(state: StudioState, dispatch: Dispatch<StudioAction>) {
  const lock = useRef(false)
  const mounted = useRef(true)
  const last = useRef('')
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  async function send(message: string) {
    if (lock.current || !message.trim() || message.length > 2000) return
    lock.current = true; last.current = message
    const requestId = crypto.randomUUID(), revision = state.revision
    dispatch({ type: 'aiStarted', requestId, message })
    const payload = { message, revision, draft: toAssistantDraft(state.draft), conversation_state: state.conversationState,
      history: state.messages.slice(-6).map(({ role, content }) => ({ role, content: content.slice(0, 1000) })) }
    const context = state.result?.assistantContext
      ? { assistant_context: state.result.assistantContext,
        ...(state.detailId ? { focused_destination_id: state.detailId } : {}) }
      : {}
    const request = (withContext: boolean) =>
      requestAssistantTurn(withContext ? { ...payload, ...context } : payload)
    try {
      let response: Awaited<ReturnType<typeof requestAssistantTurn>>
      try {
        response = await request(Object.keys(context).length > 0)
      } catch (first) {
        const stale = first instanceof ApiError && first.code === 'assistant_context_expired'
          && Object.keys(context).length > 0
        if (!stale) throw first
        response = await request(false)
      }
      if (mounted.current) dispatch({ type: 'applyAssistant', requestId, revision, response,
        resultVersion: state.result?.version ?? null, focusedId: state.detailId })
    } catch (error) {
      if (mounted.current) {
        const needsLogin = error instanceof ApiError && error.status === 401 && error.code === 'authentication_required'
        const message = needsLogin ? '登录已过期，请重新登录。原文和条件已保留。'
          : error instanceof ApiError && error.code === 'assistant_configuration_error'
            ? '当前模型未接通，请检查模型名称或可用通道。原文已保留。'
          : error instanceof ApiError && error.code === 'assistant_context_expired'
            ? '结果解读已失效，请确认更新推荐；仍可直接修改条件。'
            : 'AI暂不可用，原文已保留。可直接编辑条件继续查询。'
        dispatch({ type: 'aiFailed', requestId, message })
        if (needsLogin) requestAccountDialog()
      }
      throw new Error('assistant_unavailable', { cause: error })
    } finally { lock.current = false }
  }
  return { send, retry: () => send(last.current) }
}
