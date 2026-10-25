import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { DiscoveryLocationPill } from '../src/features/discovery/DiscoveryLocationPill'
import { apiClient } from '../src/api/client'

afterEach(() => vi.restoreAllMocks())

it('shows the actual area, opens correction in place, and selects coordinates without a chat request', async () => {
  const place = { provider_id: 'suzhou', name: '苏州站', district: '苏州市', address: '苏州',
    coordinate: { longitude: 120.6, latitude: 31.3, system: 'gcj02' } }
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ suggestions: [place] })
  const post = vi.spyOn(apiClient, 'post'), select = vi.fn(), retry = vi.fn()
  render(<DiscoveryLocationPill position={{ label: '四川省 成都市', source: 'device', approximate: false, accuracy_m: 40, captured_at: null }}
    locating={false} error='' onRetry={retry} onSelect={select} />)
  await userEvent.click(screen.getByRole('button', { name: /定位：四川省 成都市/ }))
  await userEvent.type(screen.getByLabelText('选择出发位置'), '苏州站')
  await userEvent.click(await screen.findByRole('option', { name: /苏州站/ }))
  expect(select).toHaveBeenCalledWith(place)
  expect(get).toHaveBeenCalledWith(expect.stringContaining('city='))
  expect(post).not.toHaveBeenCalled()
  expect(screen.queryByRole('region', { name: '修改位置' })).not.toBeInTheDocument()
})

it('keeps location acquisition and retry inside one capsule without a modal', async () => {
  const retry = vi.fn()
  const view = render(<DiscoveryLocationPill locating error='' onRetry={retry} onSelect={vi.fn()} />)
  expect(screen.getByRole('status')).toHaveTextContent('正在获取位置')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  view.rerender(<DiscoveryLocationPill locating={false} error='暂未取得位置 · 重试' onRetry={retry} onSelect={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: /暂未取得位置/ }))
  fireEvent.click(screen.getByRole('button', { name: '重新定位' }))
  await waitFor(() => expect(retry).toHaveBeenCalledOnce())
})
