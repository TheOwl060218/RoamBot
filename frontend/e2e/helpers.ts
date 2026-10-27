import { expect, type Page, type Route } from '@playwright/test'

export function tomorrowInChina() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(Date.now() + 86_400_000))
}

export async function openCondition(page: Page, label: string) {
  await expect(page.locator('[data-exit-snapshot]')).toHaveCount(0)
  await expect(page.locator('.spatial-workspace')).not.toHaveAttribute('data-workspace-phase', /^(toResults|toQuery)$/)
  await page.locator('.spatial-workspace').evaluate(async node => {
    await Promise.all(node.getAnimations({ subtree: true }).filter(a => a.effect?.getComputedTiming().iterations !== Infinity).map(a => a.finished.catch(() => undefined)))
  })
  const existing = page.getByRole('button', { name: new RegExp(`编辑${label}`) })
  if (await existing.isVisible()) return existing.click()
  await page.getByRole('button', { name: '更多功能', exact: true }).click()
  await page.getByRole('button', { name: '手动填写条件', exact: true }).click()
  await page.getByRole('dialog', { name: '填写条件' }).getByRole('button', { name: label === '风景' ? '想找的地方' : label, exact: true }).click()
}

export async function fillStudioConditions(page: Page, scenery = ['湖景']) {
  if (await page.getByRole('button', { name: '← 返回修改' }).isVisible()) {
    await page.getByRole('button', { name: '← 返回修改' }).click()
  }
  // UI tests edit the real form; language interpretation has its own tests.
  await openCondition(page, '出发地')
  await page.getByLabel('主出发地', { exact: true }).fill('苏州站')
  await page.getByRole('button', { name: '保存条件', exact: true }).click()
  await openCondition(page, '日期')
  await page.getByRole('button', { name: '明天', exact: true }).click()
  await page.getByRole('button', { name: '保存条件', exact: true }).click()
  await openCondition(page, '目的地范围')
  await page.getByLabel('最大距离（km）').fill('80')
  await page.getByRole('button', { name: '保存条件', exact: true }).click()
  await openCondition(page, '风景')
  await page.getByLabel('想找什么样的地方').fill(scenery.join('和'))
  // Manual form scenarios are independent of the optional language refinement.
  // Keep its command response controlled; dedicated conversation scenarios use their own transport.
  const manualMessage = `想找的地方：${scenery.join('和')}`
  const acknowledge = async (route: Route) => {
    const command = route.request().postDataJSON()
    if (command.message !== manualMessage) return route.fallback()
    return route.fulfill({ json: { request_id: command.request_id, proposal: 'manual-fixture',
      question: '条件已保存。', actions: [], requires_confirmation: false } })
  }
  const endpoint = '**/api/v1/assistant/commands/proposals'
  await page.route(endpoint, acknowledge)
  const acknowledged = page.waitForResponse(response => response.url().endsWith('/assistant/commands/proposals') && response.request().postDataJSON().message === manualMessage)
  await page.getByRole('button', { name: '保存条件', exact: true }).click()
  await acknowledged
  await expect(page.getByRole('button', { name: '开始推荐', exact: true })).toBeEnabled()
  await page.unroute(endpoint, acknowledge)
  await expect(page.getByRole('button', { name: /编辑出发地/ })).toContainText('苏州站')
  await expect(page.getByRole('button', { name: '开始推荐', exact: true })).toBeEnabled()
}
export async function submitRecommendation(page: Page) {
  await fillStudioConditions(page)
  await page.getByRole('button', { name: '开始推荐', exact: true }).click()
  await expect(page.getByTestId('destination-card').first()).toBeVisible()
  await page.getByRole('button', { name: /^了解/ }).first().click()
  await expect(page.locator('.destination-detail')).toBeVisible()
  await expect(page.getByRole('button', { name: '← 返回修改' })).toBeVisible()
  await expect(page.getByText('演示数据', { exact: true })).toBeVisible()
}

export async function registerUser(page: Page, suffix: string) {
  if (await page.getByRole('dialog').count() === 0) {
    await page.getByRole('button', { name: '账户', exact: true }).click()
  }
  await page.getByRole('tab', { name: '创建账户', exact: true }).click()
  const unique = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`
  const username = `qa_${suffix.slice(0, 5)}_${unique}`
  const auth = page.getByRole('dialog').filter({ has: page.getByRole('button', { name: '注册并登录', exact: true }) })
  await auth.getByLabel('用户名', { exact: true }).fill(username)
  await auth.getByLabel('密码', { exact: true }).fill('RoamBotDemo123!')
  await page.getByRole('button', { name: '注册并登录', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  return username
}


/** Match the real auth contract: guests receive 401, not a null user in a 200 session. */
export async function fulfillApiFixture(route: Route, options: Parameters<Route['fulfill']>[0]) {
  const body = options?.json as { user?: unknown } | undefined
  if (new URL(route.request().url()).pathname.endsWith('/auth/me') && body && 'user' in body && body.user === null) {
    return route.fulfill({ status: 401, json: { error: { code: 'authentication_required', message: '请登录', fields: [] } } })
  }
  return route.fulfill(options)
}


/** Exercise the current command envelope while preserving each UI test's controlled turn fixture. */
export async function installLegacyAssistantFixture(page: Page) {
  const planned = new Map<string, { requestId: string; assistant: unknown }>()
  await page.route('**/api/v1/assistant/commands/proposals', async route => {
    const command = route.request().postDataJSON()
    const turn = { ...command.context.assistant_turn, message: command.message }
    const upstream = await page.evaluate(async ({ turn, csrf }) => {
      const response = await fetch('/api/v1/assistant/turns', { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRF-Token': csrf } : {}) }, body: JSON.stringify(turn) })
      return { status: response.status, json: await response.json() }
    }, { turn, csrf: route.request().headers()['x-csrf-token'] })
    if (upstream.status >= 400) return route.fulfill({ status: upstream.status, json: { error: { code: upstream.json.error?.code ?? 'assistant_unavailable',
      message: upstream.status === 401 ? '登录已过期，请重新登录。' : 'AI暂不可用，原文已保留。可直接编辑条件继续查询。', fields: [] } } })
    const proposal = crypto.randomUUID()
    planned.set(proposal, { requestId: command.request_id, assistant: upstream.json })
    return route.fulfill({ json: { request_id: command.request_id, proposal, question: null,
      actions: [{ tool: 'update_search_conditions', arguments: { message: command.message } }], requires_confirmation: false } })
  })
  await page.route('**/api/v1/assistant/commands/execute', async route => {
    const body = route.request().postDataJSON(), item = planned.get(body.proposal)
    expect(item?.requestId).toBe(body.request_id)
    return route.fulfill({ json: { status: 'completed', steps: [
      { tool: 'update_search_conditions', status: 'completed', result: { assistant: item!.assistant } },
    ] } })
  })
}
