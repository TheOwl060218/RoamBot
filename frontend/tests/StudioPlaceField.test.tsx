import { act, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'

import { apiClient } from '../src/api/client'
import type { PlaceSuggestion } from '../src/api/types'
import { StudioPlaceField } from '../src/features/studio/StudioPlaceField'

afterEach(() => vi.useRealTimers())

function Host({ onSelect }: { onSelect: (place: PlaceSuggestion) => void }) {
  const [value, setValue] = useState('')
  return <StudioPlaceField label="主出发地" value={value} city="" onChange={setValue} onSelect={onSelect} />
}

it('debounces suggestions, limits the menu and preserves provider coordinates', async () => {
  vi.useFakeTimers()
  const suggestions = Array.from({ length: 6 }, (_, index) => ({
    provider_id: `place-${index}`, name: `苏州地点${index}`, district: '姑苏区', address: `地址${index}`,
    coordinate: { longitude: 120 + index, latitude: 31, system: 'gcj02' as const },
  }))
  vi.spyOn(apiClient, 'get').mockResolvedValue({ suggestions })
  const onSelect = vi.fn()
  render(<Host onSelect={onSelect} />)

  const input = screen.getByRole('combobox', { name: '主出发地' })
  fireEvent.focus(input)
  fireEvent.change(input, { target: { value: '苏州' } })
  expect(apiClient.get).not.toHaveBeenCalled()
  await act(async () => { vi.advanceTimersByTime(450); await Promise.resolve() })
  expect(apiClient.get).toHaveBeenCalledTimes(1)
  expect(screen.getAllByRole('option')).toHaveLength(5)

  fireEvent.click(screen.getAllByRole('option')[0])
  expect(onSelect).toHaveBeenCalledWith(suggestions[0])
})
