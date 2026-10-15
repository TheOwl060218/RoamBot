import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { apiClient } from '../src/api/client'
import { TravelForm } from '../src/features/search/TravelForm'
import { chinaDate, type TravelFormDraft } from '../src/features/search/formState'

it('submits a nationwide origin without a separate or hidden city restriction', () => {
  const onSubmit = vi.fn()
  render(<TravelForm onSubmit={onSubmit} />)
  expect(screen.queryByLabelText('出发城市')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('主出发地'), { target: { value: '上海站' } })
  fireEvent.click(screen.getByLabelText('湖景'))
  fireEvent.click(screen.getByRole('button', { name: '开始推荐' }))
  expect(onSubmit.mock.calls[0][0]).toMatchObject({ city: '', main_origin: '上海站' })
})

it('submits regions only in recommendation and preserves them through mode switching', () => {
  const onSubmit = vi.fn()
  const initialDraft: TravelFormDraft = { mode: 'recommendation', city: '苏州', mainOrigin: '苏州站',
    companions: [], mainOriginCoordinate: null, companionOriginCoordinates: [], maxDistance: '200',
    startDate: chinaDate(1), endDate: chinaDate(1), sceneryTypes: ['lake'], matchMode: 'any',
    targetPlace: '金鸡湖', destinationRegions: ['330100'] }
  render(<TravelForm initialDraft={initialDraft} onSubmit={onSubmit} />)
  expect(screen.getByLabelText('最大距离（km）')).toBeDisabled()
  expect(screen.getByLabelText('最大距离（km）')).toHaveValue('已按目的地范围筛选')
  fireEvent.click(screen.getByRole('button', { name: '开始推荐' }))
  expect(onSubmit.mock.calls[0][0]).toMatchObject({ destination_regions: ['330100'] })
  fireEvent.click(screen.getByRole('radio', { name: '评估指定地点' }))
  expect(screen.getByLabelText('最大距离（km）')).toHaveValue(200)
  expect(screen.queryByRole('combobox', { name: '目的地城市范围' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '评估这个地点' }))
  expect(onSubmit.mock.calls[1][0]).not.toHaveProperty('destination_regions')
  fireEvent.click(screen.getByRole('radio', { name: '推荐地点' }))
  fireEvent.click(screen.getByRole('button', { name: '开始推荐' }))
  expect(onSubmit.mock.calls[2][0]).toMatchObject({ destination_regions: ['330100'] })
})

it('unconfirmed_region_text_blocks_submit', () => {
  const onSubmit = vi.fn()
  render(<TravelForm onSubmit={onSubmit} />)
  fireEvent.change(screen.getByRole('combobox', { name: '目的地城市范围' }), { target: { value: '杭' } })
  fireEvent.click(screen.getByRole('button', { name: '开始推荐' }))
  expect(screen.getByRole('alert')).toHaveTextContent('请从候选中选择省市，或清空未选择的输入')
  expect(onSubmit).not.toHaveBeenCalled()
})

describe('TravelForm', () => {
  it('clears an outdated distance error after the value is corrected', () => {
    render(<TravelForm onSubmit={vi.fn()} />)
    const distance = screen.getByLabelText('最大距离（km）')
    fireEvent.change(distance, { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: '开始推荐' }))
    expect(distance.closest('label')?.querySelector('.field-error')).not.toBeNull()
    fireEvent.change(distance, { target: { value: '50' } })
    expect(distance.closest('label')?.querySelector('.field-error')).toBeNull()
  })
  it('places departure details before destination limits without a redundant city input', () => {
    render(<TravelForm onSubmit={vi.fn()} />)
    expect(screen.queryByLabelText('出发城市')).not.toBeInTheDocument()
    const origins = screen.getByRole('group', { name: '从哪里出发' })
    const distance = screen.getByLabelText('最大距离（km）')
    const regions = screen.getByRole('combobox', { name: '目的地城市范围' })
    const date = screen.getByLabelText('开始日期')
    for (const [first, second] of [[origins, distance], [distance, regions], [regions, date]]) {
      expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    }
  })

  it('announces all invalid fields prominently without starting a recommendation', () => {
    const onSubmit = vi.fn()
    render(<TravelForm onSubmit={onSubmit} />)
    fireEvent.change(screen.getByLabelText('最大距离（km）'), { target: { value: '500000' } })
    fireEvent.click(screen.getByRole('button', { name: '开始推荐' }))
    const bubble = screen.getByRole('alert', { name: '请检查填写内容' })
    expect(within(bubble).getByText(/主出发地/)).toBeInTheDocument()
    expect(within(bubble).getByText(/最大距离.*500/)).toBeInTheDocument()
    expect(within(bubble).getByText(/风景类型/)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('restarts the two-second bubble on repeated invalid submission without stacking', () => {
    vi.useFakeTimers()
    try {
      render(<TravelForm onSubmit={vi.fn()} />)
      const submit = screen.getByRole('button', { name: '开始推荐' })
      fireEvent.click(submit)
      expect(screen.getByRole('alert', { name: '请检查填写内容' })).toBeInTheDocument()
      act(() => vi.advanceTimersByTime(1000))
      fireEvent.click(submit)
      expect(screen.getAllByRole('alert', { name: '请检查填写内容' })).toHaveLength(1)
      act(() => vi.advanceTimersByTime(1999))
      expect(screen.getByRole('alert', { name: '请检查填写内容' })).toBeInTheDocument()
      act(() => vi.advanceTimersByTime(1))
      expect(screen.queryByRole('alert', { name: '请检查填写内容' })).not.toBeInTheDocument()
      expect(screen.getByText('请输入主出发地')).toBeInTheDocument()
    } finally { vi.useRealTimers() }
  })

  it('clears the bubble when corrected fields are successfully submitted', () => {
    const onSubmit = vi.fn()
    render(<TravelForm onSubmit={onSubmit} />)
    fireEvent.click(screen.getByRole('button', { name: '开始推荐' }))
    expect(screen.getByRole('alert', { name: '请检查填写内容' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('主出发地'), { target: { value: '苏州站' } })
    fireEvent.click(screen.getByRole('checkbox', { name: '湖景' }))
    fireEvent.click(screen.getByRole('button', { name: '开始推荐' }))
    expect(screen.queryByRole('alert', { name: '请检查填写内容' })).not.toBeInTheDocument()
    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it('announces server field errors without exposing the entered address', () => {
    const view = render(<TravelForm onSubmit={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('主出发地'), { target: { value: '私人地址' } })
    view.rerender(<TravelForm onSubmit={vi.fn()} fieldErrors={{ main_origin: '无法识别出发地，请重新选择' }} />)
    const bubble = screen.getByRole('alert', { name: '请检查填写内容' })
    expect(within(bubble).getByText(/无法识别出发地/)).toBeInTheDocument()
    expect(bubble).not.toHaveTextContent('私人地址')
  })

  it('names the affected field when server validation uses an English message', () => {
    render(<TravelForm onSubmit={vi.fn()} fieldErrors={{ main_origin: 'Origin could not be resolved.' }} />)
    const bubble = screen.getByRole('alert', { name: '请检查填写内容' })
    expect(bubble).toHaveTextContent('主出发地')
    expect(bubble).not.toHaveTextContent('Origin could not be resolved.')
  })
  it('switches between recommendation and place evaluation inputs', async () => {
    const user = userEvent.setup()
    render(<TravelForm onSubmit={vi.fn()} />)

    expect(screen.getByRole('heading', { name: '想去哪里走走？' })).toBeInTheDocument()
    expect(screen.queryByLabelText('出发城市')).not.toBeInTheDocument()
    expect(screen.getByLabelText('最大距离（km）')).toHaveValue(50)
    expect(screen.getByText('风景类型')).toBeInTheDocument()
    expect(screen.queryByLabelText('目标地点')).not.toBeInTheDocument()

    await user.click(screen.getByRole('radio', { name: '评估指定地点' }))

    expect(screen.getByLabelText('目标地点')).toBeInTheDocument()
    expect(screen.queryByText('风景类型')).not.toBeInTheDocument()
  })

  it('submits a typed recommendation request with default weights', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<TravelForm onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('主出发地'), '苏州站')
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        city: '',
        main_origin: '苏州站',
        companion_origins: [],
        max_distance_km: 50,
        scenery_types: ['lake'],
        scenery_match_mode: 'any',
        weights: { weather: 40, distance: 30, fairness: 0, popularity: 30 },
      }),
    )
  })

  it('reuses the coordinate from a selected origin suggestion', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    const getSuggestions = vi.spyOn(apiClient, 'get').mockResolvedValue({
      suggestions: [{
        provider_id: 'poi-1',
        name: '南京大学苏州校区东区',
        district: '江苏省苏州市虎丘区',
        address: '太湖大道1520号',
        coordinate: { longitude: 120.1, latitude: 31.1, system: 'gcj02' },
      }],
    })
    render(<TravelForm onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('主出发地'), '南京大学')
    await user.click(await screen.findByRole('option', { name: /南京大学苏州校区东区/ }, { timeout: 1500 }))
    await new Promise((resolve) => setTimeout(resolve, 550))
    expect(getSuggestions).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      main_origin: '南京大学苏州校区东区',
      main_origin_coordinate: { longitude: 120.1, latitude: 31.1, system: 'gcj02' },
    }))
  })

  it('does not reopen selected origin suggestions when dates change', async () => {
    const user = userEvent.setup()
    const getSuggestions = vi.spyOn(apiClient, 'get').mockResolvedValue({
      suggestions: [{
        provider_id: 'poi-1',
        name: '南京大学苏州校区东区',
        district: '江苏省苏州市虎丘区',
        address: '太湖大道1520号',
        coordinate: { longitude: 120.1, latitude: 31.1, system: 'gcj02' },
      }],
    })
    render(<TravelForm onSubmit={vi.fn()} />)

    await user.type(screen.getByLabelText('主出发地'), '南京大学')
    await user.click(await screen.findByRole('option', { name: /南京大学苏州校区东区/ }, { timeout: 1500 }))
    fireEvent.change(screen.getByLabelText('开始日期'), { target: { value: chinaDate(2) } })
    await new Promise((resolve) => setTimeout(resolve, 550))

    expect(screen.queryByRole('option')).not.toBeInTheDocument()
    expect(getSuggestions).toHaveBeenCalledTimes(1)
  })

  it('reserves twenty percent for fairness when a companion is added', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<TravelForm onSubmit={onSubmit} />)

    await user.type(screen.getByLabelText('主出发地'), '苏州站')
    await user.click(screen.getByRole('button', { name: '添加同行人' }))
    await user.type(screen.getByLabelText('同行人 1 出发地'), '苏州园区站')
    await user.click(screen.getByRole('checkbox', { name: '湖景' }))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        companion_origins: ['苏州园区站'],
        weights: { weather: 32, distance: 24, fairness: 20, popularity: 24 },
      }),
    )
  })

  it('allows clearing the maximum distance and replaces a leading zero', async () => {
    const user = userEvent.setup()
    render(<TravelForm onSubmit={vi.fn()} />)
    const input = screen.getByRole('spinbutton')

    await user.clear(input)
    expect(input).toHaveValue(null)

    await user.type(input, '0')
    expect(input).toHaveDisplayValue('0')

    await user.type(input, '200')
    expect(input).toHaveDisplayValue('200')
  })

  it('reserves stable validation message space before and after an error', async () => {
    const user = userEvent.setup()
    const { container } = render(<TravelForm onSubmit={vi.fn()} />)
    const slotsBefore = container.querySelectorAll('.field-message').length
    expect(slotsBefore).toBeGreaterThan(0)

    await user.clear(screen.getByLabelText('最大距离（km）'))
    await user.click(screen.getByRole('button', { name: '开始推荐' }))

    expect(within(container).getByText('最大距离必须在 0 到 500 km 之间')).toBeInTheDocument()
    expect(container.querySelectorAll('.field-message')).toHaveLength(slotsBefore)
  })

  it('restores the current-tab search draft after remounting', async () => {
    const user = userEvent.setup()
    const first = render(<TravelForm onSubmit={vi.fn()} />)

    await user.type(screen.getByLabelText('主出发地'), '上海人民广场')
    await user.click(screen.getByRole('radio', { name: '评估指定地点' }))
    await user.type(screen.getByLabelText('目标地点'), '上海博物馆')
    first.unmount()

    render(<TravelForm onSubmit={vi.fn()} />)

    expect(screen.queryByLabelText('出发城市')).not.toBeInTheDocument()
    expect(screen.getByLabelText('主出发地')).toHaveValue('上海人民广场')
    expect(screen.getByLabelText('目标地点')).toHaveValue('上海博物馆')
  })

  it('persists only weight preferences and restores them after remounting', () => {
    const first = render(<TravelForm onSubmit={vi.fn()} />)
    const firstBoundary = screen.getByRole('slider', { name: '天气与距离分界' })
    fireEvent.keyDown(firstBoundary, { key: 'ArrowRight' })
    fireEvent.keyDown(firstBoundary, { key: 'ArrowRight' })
    first.unmount()

    render(<TravelForm onSubmit={vi.fn()} />)

    expect(screen.getByRole('slider', { name: '天气与距离分界' })).toHaveAttribute(
      'aria-valuenow',
      '50',
    )
    expect(screen.getByText('天气适配 50%')).toBeInTheDocument()
    expect(Object.keys(localStorage)).toEqual(['roambot.ui.display-weights.v2'])
    expect(localStorage.getItem('roambot.ui.display-weights.v2')).not.toMatch(
      /fairness|苏州|origin|target/,
    )
  })

  it('keeps the visible weight split when switching search modes', async () => {
    const user = userEvent.setup()
    render(<TravelForm onSubmit={vi.fn()} />)
    const firstBoundary = screen.getByRole('slider', { name: '天气与距离分界' })
    fireEvent.keyDown(firstBoundary, { key: 'ArrowRight' })

    await user.click(screen.getByRole('radio', { name: '评估指定地点' }))
    expect(screen.getByRole('slider', { name: '天气与距离分界' })).toHaveAttribute(
      'aria-valuenow',
      '45',
    )

    await user.click(screen.getByRole('radio', { name: '推荐地点' }))
    expect(screen.getByRole('slider', { name: '天气与距离分界' })).toHaveAttribute(
      'aria-valuenow',
      '45',
    )
  })

  it('ignores preferences stored with the old four-weight format', () => {
    localStorage.setItem('roambot.ui.weights.v1', JSON.stringify({
      recommendation: { weather: 70, distance: 10, fairness: 10, popularity: 10 },
    }))

    render(<TravelForm onSubmit={vi.fn()} />)

    expect(screen.getByRole('slider', { name: '天气与距离分界' })).toHaveAttribute(
      'aria-valuenow',
      '40',
    )
  })
})
