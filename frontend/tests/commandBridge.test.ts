import { describe, expect, it } from 'vitest'
import { CommandBridge, contextFingerprint } from '../src/features/commands/commandBridge'

describe('explicit command bridge', () => {
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
    await expect(bridge.perform({ tool: 'select_candidates', arguments: {} })).rejects.toThrow()
  })

  it('detects manual edits, layer changes and cross-page movement, but ignores chat display changes', () => {
    const before = { page: '/recommend', result_version: 2, layer: 'map', selected_ids: ['a'],
      assistant_turn: { revision: 3, history: [] } }
    expect(contextFingerprint(before)).not.toBe(contextFingerprint({ ...before, layer: 'detail' }))
    expect(contextFingerprint(before)).not.toBe(contextFingerprint({ ...before, page: '/plans' }))
    expect(contextFingerprint(before)).not.toBe(contextFingerprint({
      ...before, assistant_turn: { revision: 4, history: [] },
    }))
    expect(contextFingerprint(before)).toBe(contextFingerprint({
      ...before, assistant_turn: { revision: 3, history: [{ content: '正在处理' }] },
    }))
  })
})
