import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { TravelForm } from '../src/features/search/TravelForm'

describe('search accessibility baseline', () => {
  it('labels controls and exposes keyboard-reachable modes and weights', () => {
    const { container } = render(<TravelForm onSubmit={vi.fn()} />)

    expect(screen.getByRole('radiogroup', { name: '查询模式' })).toBeInTheDocument()
    expect(screen.getByLabelText('城市')).toBeInTheDocument()
    expect(screen.getByLabelText('最大距离（km）')).toBeInTheDocument()
    expect(screen.getByLabelText('主出发地')).toBeInTheDocument()
    expect(screen.getAllByRole('slider')).toHaveLength(3)

    for (const control of container.querySelectorAll('button, input, select')) {
      expect(control).not.toHaveAttribute('tabindex', '-1')
    }
    for (const button of container.querySelectorAll('button')) {
      expect(button).toHaveAccessibleName()
    }
  })
})
