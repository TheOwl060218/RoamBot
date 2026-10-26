import { act, renderHook } from '@testing-library/react'
import { expect, it } from 'vitest'
import { useSessionMessages } from '../src/features/commands/useSessionMessages'

type Turn = { role: string; content: string }
const message: Turn = { role: 'user', content: '想找湖边走走' }
it('keeps dialogue after a component remount and explicit clearing', () => {
  const first = renderHook(() => useSessionMessages<Turn>('discovery', 'alice', true))
  act(() => first.result.current[1]([message]))
  first.unmount()
  const second = renderHook(() => useSessionMessages<Turn>('discovery', 'alice', true))
  expect(second.result.current[0]).toEqual([message])
  act(() => second.result.current[1]([]))
  second.unmount()
  const third = renderHook(() => useSessionMessages<Turn>('discovery', 'alice', true))
  expect(third.result.current[0]).toEqual([])
})
it('waits for identity before restoring and never displays another account dialogue', () => {
  const first = renderHook(() => useSessionMessages<Turn>('business', 'alice', true))
  act(() => first.result.current[1]([message])); first.unmount()
  const view = renderHook(({ owner, ready }) => useSessionMessages<Turn>('business', owner, ready),
    { initialProps: { owner: 'alice', ready: false } })
  expect(view.result.current[0]).toEqual([])
  view.rerender({ owner: 'alice', ready: true })
  expect(view.result.current[0]).toEqual([message])
  view.rerender({ owner: 'bob', ready: true })
  expect(view.result.current[0]).toEqual([])
  view.rerender({ owner: 'alice', ready: true })
  expect(view.result.current[0]).toEqual([message])
})
it('adopts guest dialogue on login without leaving it visible after logout', () => {
  const view = renderHook(({ owner }) => useSessionMessages<Turn>('discovery', owner, true),
    { initialProps: { owner: null as string | null } })
  act(() => view.result.current[1]([message]))
  view.rerender({ owner: 'alice' })
  expect(view.result.current[0]).toEqual([message])
  view.rerender({ owner: null })
  expect(view.result.current[0]).toEqual([])
})
it('keeps different history conversations separate', () => {
  const view = renderHook(({ scope }) => useSessionMessages<Turn>(scope, 'alice', true, [message]),
    { initialProps: { scope: 'history:first' } })
  act(() => view.result.current[1]([...view.result.current[0], { role: 'user', content: '改为书店' }]))
  view.rerender({ scope: 'history:second' })
  expect(view.result.current[0]).toEqual([message])
  view.rerender({ scope: 'history:first' })
  expect(view.result.current[0]).toHaveLength(2)
})
