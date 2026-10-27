import { useEffect, useRef, type Dispatch } from 'react'
import { apiClient, ApiError } from '../../api/client'
import { requestAccountDialog } from '../../app/accountDialog'
import type { RecommendationResponse, PlaceEvaluationResponse } from '../../api/types'
import { chinaDate } from '../search/formState'
import { buildStudioRequest } from './studioState'
import type { StudioAction, StudioResult, StudioState } from './types'

export function useStudioSearch(state: StudioState, dispatch: Dispatch<StudioAction>, username: string | null) {
  const lock = useRef(false), mounted = useRef(true), owner = useRef(username)
  useEffect(() => { owner.current = username }, [username])
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  async function submit() {
    if (lock.current) return
    lock.current = true
    const requestId = crypto.randomUUID(), revision = state.revision, startedOwner = username
    dispatch({ type: 'queryStarted', requestId })
    try {
      const request = buildStudioRequest(state, chinaDate(0))
      const evaluation = 'target_place' in request
      const response = await apiClient.post<RecommendationResponse | PlaceEvaluationResponse>(evaluation ? '/place-evaluations' : '/recommendations', request)
      const result: StudioResult = { version: Math.max(state.result?.version ?? 0, state.teamPick.batchVersion ?? 0, state.newQuerySnapshot?.result?.version ?? 0) + 1,
        mode: evaluation ? 'place_evaluation' : 'recommendation', items: 'items' in response ? response.items : [response.item],
        source_state: response.source_state, generated_at: response.generated_at,
        queryRequest: request, submittedRevision: revision,
        historyId: 'history_id' in response ? response.history_id ?? null : null,
        historyOwner: owner.current === startedOwner ? startedOwner : null,
        assistantContext: owner.current === startedOwner ? response.assistant_context ?? undefined : undefined }
      if (mounted.current) dispatch({ type: 'querySucceeded', requestId, revision, result })
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) requestAccountDialog()
      const message = error instanceof ApiError ? error.status === 401 ? '请先登录后再进行查询。' : '查询暂未完成，请检查条件或稍后再试。' : error instanceof Error ? error.message : '查询失败，请稍后再试。'
      if (mounted.current) dispatch({ type: 'queryFailed', requestId, message })
      throw new Error(message, { cause: error })
    } finally { lock.current = false }
  }
  return { submit }
}
