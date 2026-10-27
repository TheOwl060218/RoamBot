import { apiClient } from '../../api/client'
import type { AssistantTurnRequest, AssistantTurnResponse } from './types'

export function requestAssistantTurn(body: AssistantTurnRequest) {
  return apiClient.post<AssistantTurnResponse>('/assistant/turns', body)
}
