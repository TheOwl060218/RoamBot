import { act, renderHook } from '@testing-library/react'
import { useReducer } from 'react'
import { expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/client'
import { useStudioSearch } from '../src/features/studio/useStudioSearch'
import { createStudioState, studioReducer } from '../src/features/studio/studioState'
import { chinaDate } from '../src/features/search/formState'

it('query has immediate visible status, only one request, and ends empty result', async () => {
  let complete!: (value: unknown) => void
  const post = vi.spyOn(apiClient, 'post').mockImplementation(() => new Promise(resolve => { complete = resolve }))
  const { result } = renderHook(() => {
    const [state, dispatch] = useReducer(studioReducer, undefined, () => { const s = createStudioState(); s.draft = { ...s.draft, mainOrigin: '苏州站', startDate: chinaDate(0), endDate: chinaDate(0), sceneryTypes: ['lake'] }; return s })
    return { state, search: useStudioSearch(state, dispatch, null) }
  })
  let task!: Promise<void>
  act(() => { task = result.current.search.submit(); void result.current.search.submit() })
  expect(result.current.state.queryStatus).toBe('已开始推荐 · 正在结合天气、距离和你的偏好')
  expect(post).toHaveBeenCalledTimes(1)
  await act(async () => { complete({ items: [], source_state: { kind: 'demo', notices: [] }, generated_at: 'now' }); await task })
  expect(result.current.state.queryRequestId).toBeNull()
  expect(result.current.state.queryStatus).toContain('没有找到')
})
