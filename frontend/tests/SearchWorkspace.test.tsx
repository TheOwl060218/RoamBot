import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient, ApiError } from '../src/api/client'
import { AppShell } from '../src/app/AppShell'
import { AuthContext, type AuthContextValue } from '../src/features/auth/authContext'
import { SearchWorkspace } from '../src/features/search/SearchWorkspace'
import { saveSearchResult, saveTravelDraft } from '../src/features/search/formState'
import { seedStudioDraft, studioResponse } from './fixtures/studio'
const guest: AuthContextValue = { user: null, initializing: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }
function mount(props = {}) { return render(<AuthContext.Provider value={guest}><MemoryRouter initialEntries={['/recommend']}><AppShell><SearchWorkspace {...props} /></AppShell></MemoryRouter></AuthContext.Provider>) }
describe('progressive SearchWorkspace business regression', () => {
  beforeEach(() => vi.restoreAllMocks())
  it('dismisses the query capsule after two seconds without discarding feedback', async () => {
    vi.useFakeTimers()
    try {
      mount()
      await act(async () => { fireEvent.click(screen.getByRole('button', { name: '开始推荐' })) })
      expect(screen.getByRole('alert')).toHaveTextContent('请补充主出发地')
      act(() => vi.advanceTimersByTime(2100))
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      expect(screen.getByText('请补充主出发地。')).toBeVisible()
    } finally { vi.useRealTimers() }
  })
  it('lets a guest create their first condition manually without sending an AI request', async () => {
    const post = vi.spyOn(apiClient, 'post')
    mount()
    await userEvent.click(screen.getByRole('button', { name: '更多功能' }))
    await userEvent.click(screen.getByRole('button', { name: '手动填写条件' }))
    await userEvent.click(screen.getByRole('button', { name: '出发地', exact: true }))
    await userEvent.type(screen.getByRole('combobox', { name: '主出发地' }), '苏州站')
    await userEvent.click(screen.getByRole('button', { name: '保存条件' }))
    expect(screen.getByRole('button', { name: /编辑出发地/ })).toHaveTextContent('苏州站')
    expect(post).not.toHaveBeenCalled()
  })
  it('opens login for an expired assistant session while retaining the composer text', async () => {
    vi.spyOn(apiClient, 'post').mockRejectedValue(new ApiError(401, 'authentication_required', 'private'))
    mount()
    const composer = screen.getByRole('textbox', { name: '继续补充条件' })
    await userEvent.type(composer, '苏州10月11日')
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
    expect(await screen.findByRole('dialog', { name: '登录 RoamBot' })).toBeVisible()
    expect(composer).toHaveValue('苏州10月11日')
    expect(screen.queryByText(/AI暂不可用/)).not.toBeInTheDocument()
  })
  it('keeps direct condition editing reachable when the assistant fails before any cards exist', async () => {
    vi.spyOn(apiClient, 'post').mockRejectedValue(new ApiError(429, 'assistant_busy', 'busy'))
    mount()
    await userEvent.type(screen.getByRole('textbox', { name: '继续补充条件' }), '明天从苏州站出发')
    await userEvent.click(screen.getByRole('button', { name: '发送消息' }))
    await userEvent.click(await screen.findByRole('button', { name: '补充出发地' }))
    expect(screen.getByRole('combobox', { name: '主出发地' })).toBeVisible()
  })
  it('shows one requested editor and keeps the composer', async () => {
    seedStudioDraft(); mount(); expect(screen.queryByLabelText('主出发地')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /编辑出发地/ }))
    expect(screen.getByLabelText('主出发地')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '继续补充条件' })).toBeVisible()
  })
  it('header 推荐 preserves cached results', async () => {
    saveSearchResult(studioResponse); mount()
    await userEvent.click(screen.getByRole('link', { name: '推荐' }))
    expect(screen.getByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
  })
  it('going home keeps saved workspace', async () => {
    saveSearchResult(studioResponse); mount(); await userEvent.click(screen.getByRole('link', { name: 'RoamBot' }))
    expect(sessionStorage.getItem('roambot.studio.session.v1')).not.toBeNull()
  })
  it('queries only by explicit button and renders real results', async () => {
    seedStudioDraft(); const post = vi.spyOn(apiClient, 'post').mockResolvedValue(studioResponse); mount()
    expect(post).not.toHaveBeenCalled(); await userEvent.click(screen.getByRole('button', { name: '开始推荐' }))
    expect(await screen.findByRole('heading', { name: '金鸡湖景区' }, { timeout: 2000 })).toBeInTheDocument()
    expect(post).toHaveBeenCalledWith('/recommendations', expect.objectContaining({ main_origin: '苏州站', scenery_types: ['lake'] }))
    expect(screen.getByText('演示数据')).toBeInTheDocument()
  })
  it('validates missing conditions without HTTP', async () => {
    const post = vi.spyOn(apiClient, 'post'); mount(); await userEvent.click(screen.getByRole('button', { name: '开始推荐' }))
    expect(screen.getByRole('alert')).toHaveTextContent('请补充主出发地'); expect(post).not.toHaveBeenCalled()
  })
  it('locks double submit with immediate visible notice and no fake percentages', async () => {
    seedStudioDraft(); let finish!: (v: typeof studioResponse) => void
    const post = vi.spyOn(apiClient, 'post').mockReturnValue(new Promise(resolve => { finish = resolve })); mount()
    await userEvent.dblClick(screen.getByRole('button', { name: '开始推荐' }))
    expect(post).toHaveBeenCalledTimes(1); expect(screen.getByRole('status')).toHaveTextContent('已开始推荐')
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument(); finish(studioResponse)
    await screen.findByRole('heading', { name: '金鸡湖景区' }, { timeout: 2000 })
  })
  it('failed updates retain old results and hide private errors', async () => {
    seedStudioDraft(); saveSearchResult(studioResponse)
    vi.spyOn(apiClient, 'post').mockRejectedValue(new ApiError(503, 'unavailable', 'private')); mount()
    await userEvent.click(screen.getByRole('button', { name: '← 返回修改' }))
    await userEvent.click(await screen.findByRole('button', { name: '开始推荐' }, { timeout: 2000 }))
    expect(await screen.findByRole('alert')).not.toHaveTextContent('private')
    expect(screen.getByRole('heading', { name: '金鸡湖景区', hidden: true })).toBeInTheDocument()
  })
  it('401 opens login without leaving the workspace', async () => {
    seedStudioDraft(); vi.spyOn(apiClient, 'post').mockRejectedValue(new ApiError(401, 'unauthorized', 'private')); mount()
    await userEvent.click(screen.getByRole('button', { name: '开始推荐' }))
    expect(await screen.findByRole('dialog', { name: '登录 RoamBot' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('请先登录')
  })
  it('requested evaluation replaces cached recommendations but retains draft', () => {
    seedStudioDraft(); saveSearchResult(studioResponse); mount({ initialMode: 'place_evaluation', initialTarget: '留园' })
    expect(screen.getByRole('button', { name: '评估这个地点' })).toBeInTheDocument()
    expect(screen.getByText('留园')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '金鸡湖景区' })).not.toBeInTheDocument()
    expect(screen.getByText('苏州站')).toBeInTheDocument()
  })
  it('editor saves without query and retains other conditions', async () => {
    seedStudioDraft(); const post = vi.spyOn(apiClient, 'post'); mount()
    await userEvent.click(screen.getByRole('button', { name: /编辑目的地范围/ }))
    const input = screen.getByLabelText('最大距离（km）'); await userEvent.clear(input); await userEvent.type(input, '120')
    await userEvent.click(screen.getByRole('button', { name: '保存条件' }))
    expect(screen.getByText('苏州站')).toBeInTheDocument(); expect(post).not.toHaveBeenCalled()
  })
  it('edits result conditions in place, cancels without mutation, and queries only after explicit update', async () => {
    seedStudioDraft(); saveSearchResult(studioResponse)
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue(studioResponse)
    mount()
    const entry = { ...window.history.state }, length = window.history.length
    await userEvent.click(screen.getByRole('button', { name: /编辑目的地范围/ }))
    await userEvent.clear(screen.getByLabelText('最大距离（km）'))
    await userEvent.type(screen.getByLabelText('最大距离（km）'), '120')
    await userEvent.click(screen.getByRole('button', { name: '关闭条件编辑' }))
    expect(document.querySelector('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    expect(screen.queryByRole('button', { name: '更新推荐' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /编辑目的地范围/ }))
    expect(screen.getByLabelText('最大距离（km）')).toHaveValue(50)
    await userEvent.clear(screen.getByLabelText('最大距离（km）'))
    await userEvent.type(screen.getByLabelText('最大距离（km）'), '120')
    await userEvent.click(screen.getByRole('button', { name: '保存条件' }))
    expect(document.querySelector('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    expect(screen.getByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
    expect(window.history.state).toEqual(entry); expect(window.history.length).toBe(length)
    expect(post).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: '更新推荐' }))
    expect(post).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledWith('/recommendations', expect.objectContaining({ max_distance_km: 120 }))
  })
  it('opens supplemental preference editors without returning to query', async () => {
    saveTravelDraft({ ...seedStudioDraft(), companions: ['南京站'], companionOriginCoordinates: [null] })
    saveSearchResult(studioResponse)
    const post = vi.spyOn(apiClient, 'post')
    mount()
    await userEvent.click(screen.getByRole('button', { name: /编辑其他偏好/ }))
    await userEvent.click(screen.getByRole('button', { name: /同行出发地/ }))
    await screen.findByRole('dialog', { name: '同行出发地' })
    await userEvent.click(screen.getByRole('button', { name: '关闭条件编辑' }))
    expect(document.querySelector('.spatial-workspace')).toHaveAttribute('data-workspace-phase', 'results')
    expect(screen.getByRole('heading', { name: '金鸡湖景区' })).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })
})
