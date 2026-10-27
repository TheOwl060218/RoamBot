import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeEach, expect, it, vi } from 'vitest'

import { RegionInput } from '../src/features/search/RegionInput'
import { loadRegionCatalog } from '../src/features/search/regions'
import { OverlayHost } from '../src/features/studio/OverlayHost'

vi.mock('../src/features/search/regions', async (original) => ({
  ...await original<object>(), loadRegionCatalog: vi.fn(),
}))
const catalog = { version: 'test', data_date: '2023-06-30', regions: [
  { adcode: '320000', name: '江苏省', level: 'province' as const, province_adcode: '320000' },
  { adcode: '320500', name: '苏州市', level: 'city' as const, province_adcode: '320000' },
  { adcode: '330000', name: '浙江省', level: 'province' as const, province_adcode: '330000' },
  { adcode: '330100', name: '杭州市', level: 'city' as const, province_adcode: '330000' },
] }
function Harness({ initial = [] }: { initial?: string[] }) {
  const [value, setValue] = useState(initial)
  const [query, setQuery] = useState('')
  return <><RegionInput value={value} onChange={setValue} query={query} onQueryChange={setQuery} />
    <output data-testid='selection'>{value.join(',')}</output></>
}
beforeEach(() => vi.mocked(loadRegionCatalog).mockResolvedValue(catalog))

it.each(['input', 'option'])('Escape from %s closes only the region popup then restores editor focus', async (focus) => {
  const close = vi.fn()
  render(<OverlayHost label='目的地范围' onClose={close}><Harness initial={['330100']} /></OverlayHost>)
  const input = screen.getByRole('combobox')
  fireEvent.change(input, { target: { value: '江苏' } })
  const option = await screen.findByRole('option', { name: '江苏省', exact: true })
  const target = focus === 'input' ? input : option
  target.focus()
  fireEvent.keyDown(target, { key: 'Escape' })
  expect(screen.queryByRole('dialog', { name: '选择省市' })).not.toBeInTheDocument()
  expect(screen.getByRole('dialog', { name: '目的地范围' })).toBeInTheDocument()
  expect(close).not.toHaveBeenCalled()
  expect(input).toHaveFocus()
  expect(input).toHaveValue('江苏')
  expect(screen.getByTestId('selection')).toHaveTextContent('330100')
  fireEvent.keyDown(input, { key: 'Escape' })
  expect(close).toHaveBeenCalledOnce()
})
it('shows two selected names and summarizes extras without an add placeholder', async () => {
  render(<Harness initial={['320500', '330100', '330000']} />)
  expect(await screen.findByRole('button', { name: '移除苏州市' })).toBeVisible()
  expect(screen.getByRole('button', { name: '移除杭州市' })).toBeVisible()
  expect(screen.getByRole('button', { name: '查看全部已选地区' })).toHaveTextContent('+1')
  expect(screen.getByRole('combobox')).toHaveAttribute('placeholder', '')
})
it.each(['Backspace', 'Delete'])('empty input %s removes only the last selected region and keeps focus', async (key) => {
  render(<Harness initial={['320500', '330100']} />)
  const input = screen.getByRole('combobox')
  input.focus()
  fireEvent.keyDown(input, { key })
  expect(screen.getByTestId('selection')).toHaveTextContent(/^320500$/)
  expect(input).toHaveFocus()
  fireEvent.keyDown(input, { key })
  expect(screen.getByTestId('selection').textContent).toBe('')
  expect(input).toHaveAttribute('placeholder', '距离内不限省市')
  fireEvent.keyDown(input, { key })
  expect(screen.getByTestId('selection').textContent).toBe('')
})
it.each(['Backspace', 'Delete'])('nonempty input %s deletes text without changing regions', async (key) => {
  const user = userEvent.setup()
  render(<Harness initial={['330100']} />)
  const input = screen.getByRole('combobox')
  await user.type(input, '杭')
  if (key === 'Delete') await user.keyboard('{Home}')
  await user.keyboard(`{${key}}`)
  expect(input).toHaveValue('')
  expect(screen.getByTestId('selection')).toHaveTextContent(/^330100$/)
})
it.each(['Backspace', 'Delete'])('composition %s does not remove regions', (key) => {
  render(<Harness initial={['330100']} />)
  const input = screen.getByRole('combobox')
  fireEvent.compositionStart(input)
  expect(fireEvent.keyDown(input, { key, isComposing: true })).toBe(true)
  expect(screen.getByTestId('selection')).toHaveTextContent(/^330100$/)
})
it('directory information is collapsed by default and can be disclosed', async () => {
  const user = userEvent.setup()
  render(<Harness />)
  await user.click(screen.getByRole('button', { name: '选择省市' }))
  await screen.findByRole('listbox')
  expect(screen.queryByText(/输入只是查找/)).not.toBeInTheDocument()
  const information = screen.getByText(/目录覆盖大陆31个省级地区/)
  expect(information).not.toBeVisible()
  await user.click(screen.getByText('地区信息', { exact: true }))
  expect(information).toBeVisible()
  expect(information).toHaveTextContent('2023-06-30')
  await user.click(screen.getByText('地区信息', { exact: true }))
  expect(information).not.toBeVisible()
})
it('keeps the dropdown within the available space on its chosen side', () => {
  vi.stubGlobal('innerHeight', 900)
  const geometry = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    top: 540, bottom: 584, left: 20, right: 420, width: 400, height: 44,
  } as DOMRect)
  try {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: '选择省市' }))
    const popup = screen.getByRole('dialog', { name: '选择省市' })
    expect(parseFloat(popup.style.top) + parseFloat(popup.style.maxHeight)).toBeLessThanOrEqual(888)
  } finally {
    geometry.mockRestore()
    vi.unstubAllGlobals()
  }
})
it('typing_hang_shows_hangzhou_without_selecting', async () => {
  render(<Harness />)
  fireEvent.change(screen.getByRole('combobox'), { target: { value: '杭' } })
  expect(await screen.findByRole('option', { name: /杭州市.*浙江省/ })).toBeVisible()
  expect(screen.getByTestId('selection')).toHaveTextContent('')
})
it('enter_selects_highlighted_candidate', async () => {
  render(<Harness />)
  fireEvent.change(screen.getByRole('combobox'), { target: { value: '杭' } })
  await screen.findByRole('option', { name: /杭州市/ })
  fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter' })
  expect(screen.getByTestId('selection')).toHaveTextContent('330100')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})
it('composition_enter_does_not_select', async () => {
  render(<Harness />)
  const input = screen.getByRole('combobox')
  fireEvent.change(input, { target: { value: '杭' } })
  await screen.findByRole('option', { name: /杭州市/ })
  fireEvent.compositionStart(input)
  expect(fireEvent.keyDown(input, { key: 'Enter', isComposing: true })).toBe(true)
  expect(screen.getByTestId('selection')).toHaveTextContent('')
})
it('province_selection_merges_children', async () => {
  render(<Harness initial={['320500']} />)
  fireEvent.click(screen.getByRole('button', { name: '选择省市' }))
  fireEvent.click(await screen.findByRole('option', { name: '江苏省', exact: true }))
  expect(screen.getByTestId('selection')).toHaveTextContent(/^320000$/)
})
it('failed_catalog_can_retry', async () => {
  vi.mocked(loadRegionCatalog).mockRejectedValueOnce(new Error('offline'))
  render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: '选择省市' }))
  fireEvent.click(await screen.findByRole('button', { name: '重试加载地区' }))
  expect(await screen.findByRole('option', { name: '江苏省', exact: true })).toBeVisible()
})

it('overflow_can_open_all_selected_and_remove', async () => {
  render(<Harness initial={['320500', '330100', '330000']} />)
  fireEvent.click(screen.getByRole('button', { name: '查看全部已选地区' }))
  fireEvent.click(await screen.findByRole('button', { name: '取消选择杭州市' }))
  expect(screen.getByTestId('selection')).toHaveTextContent(/^320500,330000$/)
})

it('escape_and_outside_click_close_without_changing_selection', async () => {
  render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: '选择省市' }))
  await screen.findByRole('listbox')
  fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Escape' })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '选择省市' }))
  fireEvent.pointerDown(document.body)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByTestId('selection')).toHaveTextContent('')
})
