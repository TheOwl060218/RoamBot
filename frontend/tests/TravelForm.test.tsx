import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { apiClient } from '../src/api/client'
import { TravelForm } from '../src/features/search/TravelForm'

describe('TravelForm', () => {
  it('switches between recommendation and place evaluation inputs', async () => {
    const user = userEvent.setup()
    render(<TravelForm onSubmit={vi.fn()} />)

    expect(screen.getByRole('heading', { name: '想去哪里走走？' })).toBeInTheDocument()
    expect(screen.getByLabelText('城市')).toHaveValue('苏州')
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
        city: '苏州',
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

  it('does not reopen origin suggestions when only the city changes', async () => {
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
    await user.clear(screen.getByLabelText('城市'))
    await user.type(screen.getByLabelText('城市'), '上海')
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

    expect(screen.getByText('最大距离必须在 0 到 500 km 之间')).toBeInTheDocument()
    expect(container.querySelectorAll('.field-message')).toHaveLength(slotsBefore)
  })

  it('restores the current-tab search draft after remounting', async () => {
    const user = userEvent.setup()
    const first = render(<TravelForm onSubmit={vi.fn()} />)

    await user.clear(screen.getByLabelText('城市'))
    await user.type(screen.getByLabelText('城市'), '上海')
    await user.type(screen.getByLabelText('主出发地'), '人民广场')
    await user.click(screen.getByRole('radio', { name: '评估指定地点' }))
    await user.type(screen.getByLabelText('目标地点'), '上海博物馆')
    first.unmount()

    render(<TravelForm onSubmit={vi.fn()} />)

    expect(screen.getByLabelText('城市')).toHaveValue('上海')
    expect(screen.getByLabelText('主出发地')).toHaveValue('人民广场')
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
