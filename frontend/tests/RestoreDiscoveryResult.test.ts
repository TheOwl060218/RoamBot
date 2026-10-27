import { afterEach, expect, it, vi } from 'vitest'
import { apiClient, ApiError } from '../src/api/client'
import { restoreDiscoveryResult } from '../src/features/discovery/restoreDiscoveryResult'
import type { DiscoverySnapshot } from '../src/features/discovery/types'

afterEach(() => vi.restoreAllMocks())
const missing = () => new ApiError(404, 'discovery_not_found', 'expired')
const restored = { id: 'rebound', status: 'completed', history_id: 'history', cards: [], search_request: '北京吃特色菜' } as unknown as DiscoverySnapshot

it('restores the exact saved history when an owned job expires, without a new search', async () => {
  vi.spyOn(apiClient, 'get').mockRejectedValue(missing())
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue(restored)
  expect(await restoreDiscoveryResult({ id: 'expired', history_id: 'history', message: '换一批' }, true)).toEqual({ snapshot: restored, message: '北京吃特色菜' })
  expect(post).toHaveBeenCalledExactlyOnceWith('/discovery/history/history/restore')
})

it('recovers the latest owned discovery when the old tab reference has no history id', async () => {
  const get = vi.spyOn(apiClient, 'get').mockRejectedValueOnce(missing()).mockResolvedValue({ histories: [
    { id: 'legacy', mode: 'recommendation', item_count: 4, created_at: '2026-10-25T12:00:00Z' },
    { id: 'old', mode: 'discovery', item_count: 3, created_at: '2026-10-24T12:00:00Z' },
    { id: 'latest', mode: 'discovery', item_count: 10, created_at: '2026-10-25T11:00:00Z' },
  ] })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue(restored)
  await restoreDiscoveryResult({ id: 'expired', message: '旧想法' }, true)
  expect(get).toHaveBeenLastCalledWith('/history')
  expect(post).toHaveBeenCalledExactlyOnceWith('/discovery/history/latest/restore')
})

it('restores account history even when there is no tab reference', async () => {
  vi.spyOn(apiClient, 'get').mockResolvedValue({ histories: [{ id: 'latest', mode: 'discovery', item_count: 2, created_at: '2026-10-25' }] })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue(restored)
  await restoreDiscoveryResult(null, true)
  expect(post).toHaveBeenCalledExactlyOnceWith('/discovery/history/latest/restore')
})

it('keeps network failures visible without switching to an unrelated historical result', async () => {
  const get = vi.spyOn(apiClient, 'get').mockRejectedValue(new ApiError(0, 'network_unavailable', 'offline'))
  const post = vi.spyOn(apiClient, 'post')
  await expect(restoreDiscoveryResult({ id: 'owned', history_id: 'history', message: '想法' }, true)).rejects.toMatchObject({ code: 'network_unavailable' })
  expect(get).toHaveBeenCalledTimes(1)
  expect(post).not.toHaveBeenCalled()
})

it('never reads private account history for a guest', async () => {
  const get = vi.spyOn(apiClient, 'get').mockRejectedValue(missing())
  const post = vi.spyOn(apiClient, 'post')
  expect(await restoreDiscoveryResult({ id: 'guest', history_id: 'not-authorized', message: '想法' }, false)).toBeNull()
  expect(get).toHaveBeenCalledTimes(1)
  expect(post).not.toHaveBeenCalled()
})
