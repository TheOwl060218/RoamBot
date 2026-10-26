import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeAll, beforeEach, expect, it, vi } from 'vitest'
import { apiClient } from '../src/api/client'
import { AuthContext } from '../src/features/auth/authContext'
import { PlansPage } from '../src/features/plans/PlanPages'
import { SearchPage } from '../src/pages/SearchPage'
import { DiscoveryPage } from '../src/pages/DiscoveryPage'
import { saveSearchResult } from '../src/features/search/formState'
import { seedStudioDraft, studioResponse } from './fixtures/studio'

beforeAll(() => {
  Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(this:HTMLDialogElement){this.setAttribute('open','')}})
  Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value:function(this:HTMLDialogElement){this.removeAttribute('open')}})
})
beforeEach(() => { vi.restoreAllMocks(); vi.spyOn(apiClient,'get').mockResolvedValue({plans:[],favorites:[]});seedStudioDraft();saveSearchResult(studioResponse) })
function RouteState() { const route = useLocation(); return <output aria-label='推荐入口状态'>{JSON.stringify(route.state)}</output> }
function mount(path='/recommend') {
  return render(<AuthContext.Provider value={{user:{username:'owner'},initializing:false,login:vi.fn(),register:vi.fn(),logout:vi.fn()}}>
    <MemoryRouter initialEntries={[path]}><Routes>
      <Route path='/plans' element={<PlansPage/>}/><Route path='/recommend' element={<SearchPage/>}/>
      <Route path='/explore' element={<><DiscoveryPage/><RouteState/></>}/>
      <Route path='/plans/new-plan' element={<h1>新计划详情</h1>}/>
    </Routes></MemoryRouter></AuthContext.Provider>)
}
it('starts picking from the plan center in discovery while keeping legacy queries separate',async()=>{
  mount('/plans');await screen.findByText('还没有进行中的计划')
  await userEvent.click(screen.getByRole('link',{name:'发起同行计划'}))
  expect(await screen.findByRole('heading',{name:'想去哪儿？'})).toBeVisible()
  expect(screen.getByLabelText('推荐入口状态')).toHaveTextContent('"startTeamPick":true')
  expect(screen.queryByText('同行挑选中')).not.toBeInTheDocument()
  expect(screen.getByRole('textbox',{name:'继续补充条件'})).toBeVisible()
})
it('creates directly from comparison candidates and continues after refreshing cache',async()=>{
  const post=vi.spyOn(apiClient,'post').mockImplementation(async(path)=>path==='/recommendations'?{...studioResponse,history_id:'fresh-history'}:{plan:{id:'new-plan'}})
  mount();await userEvent.click(screen.getByRole('button',{name:'加入候选：金鸡湖景区'}));await userEvent.click(screen.getByRole('button',{name:'加入候选：苏州博物馆'}))
  await userEvent.click(screen.getByRole('button',{name:'发起同行计划',exact:true}))
  await userEvent.click(screen.getByRole('button',{name:'更新推荐并继续'}))
  const dialog=screen.getByRole('dialog',{name:'创建同行计划'})
  expect(await within(dialog).findByRole('button',{name:'确认创建'})).toBeEnabled()
  expect(screen.getByRole('button',{name:'查看对比（2）'})).toBeInTheDocument()
  expect(post).not.toHaveBeenCalledWith('/plans',expect.anything())
  await userEvent.click(within(dialog).getByRole('button',{name:'确认创建'}))
  expect(await screen.findByRole('heading',{name:'新计划详情'})).toBeVisible()
  expect(post).toHaveBeenCalledWith('/plans',expect.objectContaining({history_id:'fresh-history',candidate_ids:['place-0','place-1']}))
})
it('opens detail conversation and Escape collapses it before closing the detail',async()=>{
  mount();await userEvent.click(screen.getByRole('button',{name:'了解金鸡湖景区'}))
  await userEvent.click(screen.getByRole('button',{name:'打开详情对话'}))
  const conversation=screen.getByRole('region',{name:'详情对话'})
  const input=within(conversation).getByRole('textbox',{name:'继续补充条件'})
  await userEvent.type(input,'路程再近一点');await userEvent.keyboard('{Escape}')
  expect(screen.getByRole('dialog',{name:'金鸡湖景区详情'})).toBeVisible()
  await userEvent.click(screen.getByRole('button',{name:'打开详情对话'}))
  expect(within(screen.getByRole('region',{name:'详情对话'})).getByRole('textbox',{name:'继续补充条件'})).toHaveValue('路程再近一点')
})
