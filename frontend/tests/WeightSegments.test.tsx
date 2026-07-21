import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { WeightSegments } from '../src/features/search/WeightSegments'
import {
  defaultDisplayWeights,
  type DisplayWeights,
} from '../src/features/search/formState'

function Harness({ initial = defaultDisplayWeights }: { initial?: DisplayWeights }) {
  const [value, setValue] = useState(initial)
  return (
    <WeightSegments
      value={value}
      onChange={setValue}
      onReset={() => setValue(defaultDisplayWeights)}
    />
  )
}

describe('WeightSegments', () => {
  it('uses two boundaries to present three percentages totaling one hundred', () => {
    render(<Harness />)

    const handles = screen.getAllByRole('slider')
    expect(handles).toHaveLength(2)
    expect(handles[0]).toHaveAttribute('aria-valuenow', '40')
    expect(handles[1]).toHaveAttribute('aria-valuenow', '70')
    expect(screen.getByText('天气适配 40%')).toBeInTheDocument()
    expect(screen.getByText('距离远近 30%')).toBeInTheDocument()
    expect(screen.getByText('景区热度 30%')).toBeInTheDocument()
  })

  it('moves adjacent proportions in five-percent keyboard steps', () => {
    render(<Harness />)
    const first = screen.getByRole('slider', { name: '天气与距离分界' })
    const second = screen.getByRole('slider', { name: '距离与热度分界' })

    fireEvent.keyDown(first, { key: 'ArrowRight' })
    expect(screen.getByText('天气适配 45%')).toBeInTheDocument()
    expect(screen.getByText('距离远近 25%')).toBeInTheDocument()

    fireEvent.keyDown(second, { key: 'ArrowLeft' })
    expect(screen.getByText('距离远近 20%')).toBeInTheDocument()
    expect(screen.getByText('景区热度 35%')).toBeInTheDocument()
  })

  it('does not cross boundaries and permits a zero-width middle segment', () => {
    render(<Harness initial={{ weather: 40, distance: 0, popularity: 60 }} />)
    const first = screen.getByRole('slider', { name: '天气与距离分界' })
    const second = screen.getByRole('slider', { name: '距离与热度分界' })

    expect(first).toHaveAttribute('aria-valuenow', '40')
    expect(second).toHaveAttribute('aria-valuenow', '40')
    expect(first).toHaveClass('weight-handle-first', 'weight-handle-overlap')
    expect(second).toHaveClass('weight-handle-second', 'weight-handle-overlap')
    fireEvent.keyDown(first, { key: 'ArrowRight' })
    fireEvent.keyDown(second, { key: 'ArrowLeft' })

    expect(first).toHaveAttribute('aria-valuenow', '40')
    expect(second).toHaveAttribute('aria-valuenow', '40')
    expect(screen.getByText('距离远近 0%')).toBeInTheDocument()
  })

  it('restores the shared default proportions', () => {
    render(<Harness initial={{ weather: 50, distance: 20, popularity: 30 }} />)

    fireEvent.click(screen.getByRole('button', { name: '恢复默认' }))

    expect(screen.getByText('天气适配 40%')).toBeInTheDocument()
    expect(screen.getByText('距离远近 30%')).toBeInTheDocument()
    expect(screen.getByText('景区热度 30%')).toBeInTheDocument()
  })
})
