import { useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { apiClient, ApiError } from '../src/api/client'
import { CommandRoot } from '../src/features/commands/CommandRoot'
import { useCommandTarget } from '../src/features/commands/commandContext'

afterEach(() => vi.restoreAllMocks())

const proposal = (requires_confirmation = false) => ({ request_id: 'test-command-request',
  proposal: 'test-proposal', question: null, requires_confirmation,
  actions: [{ tool: requires_confirmation ? 'delete_history' : 'list_favorites', arguments: {} }] })

function Page() {
  const [version, setVersion] = useState(1)
  useCommandTarget('test-page', () => ({ resource_version: String(version) }), () => false)
  return <button onClick={() => setVersion(v => v + 1)}>手动修改</button>
}
function mount() {
  return render(<MemoryRouter initialEntries={['/plans']}><Routes><Route element={<CommandRoot />}>
    <Route path='/plans' element={<Page />} />
    <Route path='/favorites' element={<h1>收藏页面</h1>} />
  </Route></Routes></MemoryRouter>)
}
async function input(message: string) {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '打开操作助手' }))
  await user.type(screen.getByRole('textbox', { name: '继续补充条件' }), message)
  await user.click(screen.getByRole('button', { name: '发送消息' }))
  return user
}

describe('business chat execution', () => {
  it('allows a new proposal after a known rejection without replaying any mutation', async () => {
    let proposals = 0
    const post = vi.spyOn(apiClient, 'post').mockImplementation(async path => {
      if (path.endsWith('/proposals')) {
        if (++proposals === 1) throw new ApiError(503, 'timeout', '模型超时')
        return proposal() as never
      }
      return { status: 'completed', steps: [] } as never
    })
    mount()
    const user = await input('查看收藏')
    expect((await screen.findAllByText('模型超时')).length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: '发送消息' }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(3))
    const calls = post.mock.calls.filter(([path]) => path.endsWith('/proposals'))
    expect((calls[1][1] as { request_id: string }).request_id).not.toEqual(
      (calls[0][1] as { request_id: string }).request_id)
    expect(post.mock.calls.filter(([path]) => path.endsWith('/execute'))).toHaveLength(1)
  })

  it('applies a returned navigation action through the router', async () => {
    const post = vi.spyOn(apiClient, 'post').mockImplementation(async path => {
      if (path.endsWith('/proposals')) return proposal() as never
      return { status: 'completed', steps: [{ tool: 'list_favorites', status: 'completed',
        result: { effect: { tool: 'navigate', arguments: { page: 'favorites' } } } }] } as never
    })
    mount()
    await input('查看收藏')
    expect(await screen.findByRole('heading', { name: '收藏页面' })).toBeInTheDocument()
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
  })

  it('does not send destructive execution until the user confirms', async () => {
    const post = vi.spyOn(apiClient, 'post').mockImplementation(async path =>
      (path.endsWith('/proposals') ? proposal(true) :
        { status: 'completed', steps: [{ tool: 'delete_history', status: 'completed', result: {} }] }) as never)
    mount()
    const user = await input('删除这条历史')
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()
    expect(post).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: '确认执行' }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    expect(post.mock.calls[1][1]).toMatchObject({ confirmed: true })
    expect(await screen.findByText('删除历史已完成。')).toBeInTheDocument()
  })

  it('stops before execution when the user edits state while planning', async () => {
    let release: (value: unknown) => void = () => undefined
    const post = vi.spyOn(apiClient, 'post').mockImplementation(() =>
      new Promise(resolve => { release = resolve }) as never)
    mount()
    const user = await input('查看收藏')
    await user.click(screen.getByRole('button', { name: '手动修改' }))
    release(proposal())
    expect(await screen.findByText('页面、条件或选择已变化，请重新发起操作。')).toBeInTheDocument()
    expect(post).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('heading', { name: '收藏页面' })).not.toBeInTheDocument()
  })

  it('reuses the proposal after a lost execution response instead of creating another task', async () => {
    let executions = 0
    const post = vi.spyOn(apiClient, 'post').mockImplementation(async path => {
      if (path.endsWith('/proposals')) return proposal() as never
      executions++
      if (executions === 1) throw new TypeError('response lost after commit')
      return { status: 'completed', steps: [{ tool: 'create_plan_from_selection',
        status: 'completed', result: {} }] } as never
    })
    mount()
    const user = await input('创建计划')
    expect((await screen.findAllByText('response lost after commit')).length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: '发送消息' }))
    await waitFor(() => expect(executions).toBe(2))
    expect(post.mock.calls.filter(([path]) => path.endsWith('/proposals'))).toHaveLength(1)
    const calls = post.mock.calls.filter(([path]) => path.endsWith('/execute'))
    expect(calls[1][1]).toEqual(calls[0][1])
  })

  it('includes the preceding clarification when a user answers outside the recommendation page', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
      ...proposal(), actions: [], question: '要修改哪个计划？',
    } as never)
    mount()
    const user = await input('改个名字')
    expect(await screen.findByText('要修改哪个计划？')).toBeInTheDocument()
    await user.type(screen.getByRole('textbox', { name: '继续补充条件' }), '第一个，叫周末出游')
    await user.click(screen.getByRole('button', { name: '发送消息' }))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(2))
    expect(post.mock.calls[1][1]).toMatchObject({ context: { conversation: [
      { role: 'user', content: '改个名字' }, { role: 'assistant', content: '要修改哪个计划？' },
    ] } })
  })
})
