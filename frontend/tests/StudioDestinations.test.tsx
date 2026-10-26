import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../src/features/auth/authContext'
import { StudioWorkspace } from '../src/features/studio/StudioWorkspace'
import { presentDestination } from '../src/features/studio/destinationPresentation'
import { apiClient } from '../src/api/client'
import { saveSearchResult } from '../src/features/search/formState'
import { studioResponse } from './fixtures/studio'
function mount() {
  saveSearchResult(studioResponse)
  return render(<AuthContext.Provider value={{ user: null, initializing: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }}><StudioWorkspace /></AuthContext.Provider>)
}
describe('layered destinations', () => {
  it('shows all returned items in one row without extra requests', async () => {
    const post = vi.spyOn(apiClient, 'post'); post.mockClear(); mount()
    expect(screen.getAllByTestId('destination-card')).toHaveLength(4)
    expect(post).not.toHaveBeenCalled()
  })
  it('opens details with weather expanded by default and exposes the conversation orb', async () => {
    mount(); await userEvent.click(screen.getByRole('button', { name: '了解金鸡湖景区' }))
    expect(screen.getByRole('region', { name: '金鸡湖景区详情' })).toBeInTheDocument()
    expect(screen.getByText('18–25°C')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: '打开详情对话' }))
    expect(screen.getByRole('textbox', { name: '继续补充条件' })).toBeVisible()
  })
  it('returns from a detail when pressing outside the card', async () => {
    mount(); const trigger = screen.getByRole('button', { name: '了解金鸡湖景区' })
    await userEvent.click(trigger)
    const layer = document.querySelector('.destination-detail-layer')!
    await userEvent.pointer([{ target: layer, keys: '[MouseLeft>]' }, { target: layer, keys: '[/MouseLeft]' }])
    expect(screen.queryByRole('region', { name: '金鸡湖景区详情' })).not.toBeInTheDocument()
  })
  it('same selection drives comparison, max3 and deselection', async () => {
    mount()
    for (const name of ['金鸡湖景区', '苏州博物馆', '留园']) await userEvent.click(screen.getByRole('button', { name: `加入候选：${name}` }))
    expect(screen.getByRole('button', { name: '加入候选：虎丘' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: '查看对比（3）' }))
    expect(screen.getByRole('region', { name: '候选对比' })).toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: '移出候选：苏州博物馆' })[0])
    expect(screen.getByRole('button', { name: '查看对比（2）' })).toBeInTheDocument()
  })
  it('ties do not invent an exclusive advantage or missing rating', () => {
    const a = studioResponse.items[0]
    const tie = { ...a, destination: { ...a.destination, provider_id: 'tie', rating: null } }
    expect(presentDestination(a, [a, tie]).advantages).not.toContain('路程最短')
    expect(presentDestination(tie, [a, tie]).rating).toBe('暂无评分')
  })
})
