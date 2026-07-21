import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

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

  it('persists only weight preferences and restores them after remounting', () => {
    const first = render(<TravelForm onSubmit={vi.fn()} />)
    fireEvent.change(screen.getByRole('slider', { name: '天气适配权重' }), {
      target: { value: '50' },
    })
    first.unmount()

    render(<TravelForm onSubmit={vi.fn()} />)

    expect(screen.getByRole('slider', { name: '天气适配权重' })).toHaveValue('50')
    expect(Object.keys(localStorage)).toEqual(['roambot.ui.display-weights.v2'])
    expect(localStorage.getItem('roambot.ui.display-weights.v2')).not.toMatch(
      /fairness|苏州|origin|target/,
    )
  })

  it('ignores preferences stored with the old four-weight format', () => {
    localStorage.setItem('roambot.ui.weights.v1', JSON.stringify({
      recommendation: { weather: 70, distance: 10, fairness: 10, popularity: 10 },
    }))

    render(<TravelForm onSubmit={vi.fn()} />)

    expect(screen.getByRole('slider', { name: '天气适配权重' })).toHaveValue('40')
  })
})
