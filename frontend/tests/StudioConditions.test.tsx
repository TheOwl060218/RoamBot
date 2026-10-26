import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { ConditionEditor } from '../src/features/studio/ConditionEditor'
import { ConditionPuzzle } from '../src/features/studio/ConditionPuzzle'
import { createStudioState } from '../src/features/studio/studioState'
import { loadRegionCatalog } from '../src/features/search/regions'
vi.mock('../src/features/search/regions', () => ({ loadRegionCatalog: vi.fn() }))

it('keeps the editor minimal: save only, no cancel or in-editor removal', () => {
  const save = vi.fn()
  const close = vi.fn()
  render(<ConditionEditor conditionKey='dates' draft={createStudioState().draft} onSave={save} onClose={close} />)
  fireEvent.click(screen.getByRole('button', { name: '保存条件' }))
  expect(save).toHaveBeenCalledOnce()
  expect(screen.queryByRole('button', { name: '取消' })).toBeNull()
  expect(screen.queryByRole('button', { name: '移除此条件' })).toBeNull()
})

it.each(['close', 'escape', 'outside'])('does not commit evaluation mode when cancelled via %s', (method) => {
  const original = createStudioState().draft
  const save = vi.fn(), close = vi.fn()
  render(<ConditionEditor conditionKey='targetPlace' draft={original} onSave={save} onClose={close} />)
  expect(screen.getByRole('combobox', { name: '查询方式' })).toHaveValue('place_evaluation')
  const input = screen.getByRole('combobox', { name: '目标地点' })
  fireEvent.change(input, { target: { value: '尚未保存的地点' } })
  if (method === 'close') fireEvent.click(screen.getByRole('button', { name: '关闭条件编辑' }))
  else if (method === 'escape') fireEvent.keyDown(input, { key: 'Escape' })
  else {
    fireEvent.pointerDown(screen.getByTestId('overlay-backdrop'))
    fireEvent.pointerUp(screen.getByTestId('overlay-backdrop'))
  }
  expect(close).toHaveBeenCalledOnce()
  expect(save).not.toHaveBeenCalled()
  expect(original).toMatchObject({ mode: 'recommendation', targetPlace: '' })
})

it('commits the evaluation mode and target together only on Save', () => {
  const original = createStudioState().draft, save = vi.fn()
  render(<ConditionEditor conditionKey='targetPlace' draft={original} onSave={save} onClose={vi.fn()} />)
  fireEvent.change(screen.getByRole('combobox', { name: '目标地点' }), { target: { value: '金鸡湖' } })
  fireEvent.click(screen.getByRole('button', { name: '保存条件' }))
  expect(save).toHaveBeenCalledWith(expect.objectContaining({ mode: 'place_evaluation', targetPlace: '金鸡湖' }))
  expect(original).toMatchObject({ mode: 'recommendation', targetPlace: '' })
})

it('opens all supplemental preferences from the compact rail', () => {
  const state = createStudioState()
  state.draft.companions = ['上海站']
  const open = vi.fn()
  render(<ConditionPuzzle state={state} layout='compact' onEdit={vi.fn()} onOther={open} />)
  fireEvent.click(screen.getByRole('button', { name: /编辑其他偏好/ }))
  expect(open).toHaveBeenCalledOnce()
})

it('summarizes two chosen names and the remainder rather than only a count', async () => {
  vi.mocked(loadRegionCatalog).mockResolvedValue({ version: 'test', data_date: '2026-10-11', regions: [
    { adcode: '310000', name: '上海市', level: 'province', province_adcode: '310000' },
    { adcode: '320500', name: '苏州市', level: 'city', province_adcode: '320000' },
    { adcode: '330100', name: '杭州市', level: 'city', province_adcode: '330000' },
  ] })
  const state = createStudioState()
  state.draft.destinationRegions = ['310000', '320500', '330100']
  render(<ConditionPuzzle state={state} onEdit={vi.fn()} />)
  expect(await screen.findByRole('button', { name: /上海市 · 苏州市 · \+1/ })).toBeVisible()
})

it('shows one condition per key and only relevant editor', () => {
  const state = createStudioState()
  state.draft.mainOrigin = '苏州站'
  const edit = vi.fn()
  render(<ConditionPuzzle state={state} onEdit={edit} />)
  fireEvent.click(screen.getByRole('button', { name: /编辑出发地/ }))
  expect(edit).toHaveBeenCalledWith('mainOrigin')
  expect(screen.getAllByRole('button', { name: /编辑出发地/ })).toHaveLength(1)
})

it('shows no empty cards and removes a confirmed condition', () => {
  const state = createStudioState()
  const remove = vi.fn()
  const { rerender } = render(<ConditionPuzzle state={state} onEdit={vi.fn()} onRemove={remove} />)
  expect(screen.queryByRole('button', { name: /编辑出发地/ })).toBeNull()
  state.draft.mainOrigin = '苏州站'
  rerender(<ConditionPuzzle state={state} onEdit={vi.fn()} onRemove={remove} />)
  fireEvent.click(screen.getByRole('button', { name: '移除出发地' }))
  expect(remove).toHaveBeenCalledWith('mainOrigin')
})
it('edits a freeform scenery preference instead of six checkboxes', () => {
  const save = vi.fn()
  render(<ConditionEditor conditionKey='sceneryTypes' draft={createStudioState().draft} onSave={save} onClose={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('想找什么样的地方'), { target: { value: '安静的水边，适合散步' } })
  fireEvent.click(screen.getByRole('button', { name: '保存条件' }))
  expect(save).toHaveBeenCalledWith(expect.objectContaining({ sceneryQuery: '安静的水边，适合散步', sceneryTypes: ['lake', 'park'] }))
  expect(screen.queryByRole('checkbox')).toBeNull()
})
it('switches the condition puzzle to a compact result strip', () => {
  const state = createStudioState()
  const { rerender } = render(<ConditionPuzzle state={state} onEdit={vi.fn()} />)
  expect(document.querySelector('.condition-puzzle-corner')).toBeInTheDocument()
  rerender(<ConditionPuzzle state={state} onEdit={vi.fn()} layout='compact' />)
  expect(document.querySelector('.condition-puzzle-compact')).toBeInTheDocument()
})
it('numeric distance can be cleared and saved; other editors remain absent', () => {
  const onSave = vi.fn()
  render(<ConditionEditor conditionKey='range' draft={createStudioState().draft} onSave={onSave} onClose={vi.fn()} />)
  const input = screen.getByLabelText('最大距离（km）')
  fireEvent.change(input, { target: { value: '' } })
  expect(input).toHaveValue(null)
  fireEvent.change(input, { target: { value: '200' } })
  fireEvent.click(screen.getByRole('button', { name: '保存条件' }))
  expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ maxDistance: '200' }))
  expect(screen.queryByLabelText('主出发地')).not.toBeInTheDocument()
})

it('opens the condition editor as a centered modal and cancels its local draft', () => {
  const original = createStudioState().draft
  const onSave = vi.fn()
  const onClose = vi.fn()
  render(<ConditionEditor conditionKey='mainOrigin' draft={original} onSave={onSave} onClose={onClose} />)
  const input = screen.getByRole('combobox', { name: '主出发地' })
  expect(input).toHaveFocus()
  fireEvent.change(input, { target: { value: '尚未保存的地址' } })
  fireEvent.mouseDown(document.querySelector('.studio-editor-backdrop')!)
  fireEvent.mouseUp(document.querySelector('.studio-editor-backdrop')!)
  fireEvent.click(document.querySelector('.studio-editor-backdrop')!)
  expect(onClose).toHaveBeenCalled()
  expect(onSave).not.toHaveBeenCalled()
  expect(original.mainOrigin).toBe('')
})
