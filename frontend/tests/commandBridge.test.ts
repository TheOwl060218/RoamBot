import { describe, expect, it } from 'vitest'
import { CommandBridge, contextFingerprint } from '../src/features/commands/commandBridge'

describe('explicit command bridge', () => {
  it('retains the most recent result source without mixing it into a mounted result page', () => {
    const bridge = new CommandBridge()
    const old = bridge.register('studio', () => ({ history_id: 'legacy', selected_ids: ['old'] }), () => false)
    old()
    const current = bridge.register('discovery', () => ({ discovery_job_id: 'fresh', selected_ids: ['p1', 'p2'] }), () => false)
    expect(bridge.previousResultContext()).toBeUndefined()
    current()
    bridge.register('favorites', () => ({ visible_resources: [] }), () => false)
    expect(bridge.previousResultContext()).toEqual({ discovery_job_id: 'fresh', selected_ids: ['p1', 'p2'] })
  })
  it('does not expose another account context or resurrect it through a late cleanup', () => {
    let owner: string | null = 'first'
    const bridge = new CommandBridge(() => owner)
    const leave = bridge.register('discovery', () => ({ discovery_job_id: 'private' }), () => false)
    owner = 'second'
    expect(bridge.previousResultContext()).toBeUndefined()
    bridge.clearPreviousContexts()
    leave()
    owner = 'first'
    expect(bridge.previousResultContext()).toBeUndefined()
    expect(bridge.previousContext('discovery')).toBeUndefined()
  })
  it('guards an already retained result before account cleanup runs', () => {
    let owner = 'first'
    const bridge = new CommandBridge(() => owner)
    bridge.register('discovery', () => ({ discovery_job_id: 'private' }), () => false)()
    expect(bridge.previousResultContext()).toEqual({ discovery_job_id: 'private' })
    owner = 'second'
    expect(bridge.previousResultContext()).toBeUndefined()
    expect(bridge.previousContext('discovery')).toBeUndefined()
  })
  it('waits for initial page data without suppressing later version changes', async () => {
    const bridge = new CommandBridge()
    let loading = true
    bridge.register('plan', () => ({ page_loading: loading, resource_version: loading ? null : 'loaded' }), () => false)
    let ready = false
    const waiting = bridge.whenReady().then(() => { ready = true })
    await Promise.resolve()
    expect(ready).toBe(false)
    loading = false
    await waiting
    expect(ready).toBe(true)
    expect(bridge.context().resource_version).toBe('loaded')
  })
  it('routes registered actions and reports unsupported actions instead of claiming success', async () => {
    const bridge = new CommandBridge()
    let selected: string[] = []
    const remove = bridge.register('studio', () => ({ result_version: 2 }), effect => {
      if (effect.tool !== 'select_candidates') return false
      selected = effect.arguments.ids as string[]
      return true
    })
    await bridge.perform({ tool: 'select_candidates', arguments: { ids: ['a', 'b'] } })
    expect(selected).toEqual(['a', 'b'])
    expect(bridge.context().result_version).toBe(2)
    await expect(bridge.perform({ tool: 'unknown', arguments: {} })).rejects.toThrow()
    remove()
    expect(bridge.previousContext('studio')).toEqual({ result_version: 2 })
    await expect(bridge.perform({ tool: 'select_candidates', arguments: {} })).rejects.toThrow()
  })

  it('detects manual edits, layer changes and cross-page movement, but ignores chat display changes', () => {
    const before = { page: '/recommend', result_version: 2, layer: 'map', selected_ids: ['a'],
      assistant_turn: { revision: 3, history: [] } }
    expect(contextFingerprint(before)).not.toBe(contextFingerprint({ ...before, layer: 'detail' }))
    expect(contextFingerprint(before)).not.toBe(contextFingerprint({ ...before, page: '/plans' }))
    expect(contextFingerprint({ ...before, discovery_job_id: 'old' })).not.toBe(
      contextFingerprint({ ...before, discovery_job_id: 'new' }))
    expect(contextFingerprint(before)).not.toBe(contextFingerprint({
      ...before, assistant_turn: { revision: 4, history: [] },
    }))
    expect(contextFingerprint(before)).toBe(contextFingerprint({
      ...before, assistant_turn: { revision: 3, history: [{ content: '正在处理' }] },
    }))
  })
})
