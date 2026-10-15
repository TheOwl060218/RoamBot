import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { RecommendationItem } from '../src/api/types'
import { CandidateComparison } from '../src/features/search/CandidateComparison'
import { compareCandidates } from '../src/features/search/compareLogic'

function candidate(
  id: string,
  name: string,
  score: Partial<RecommendationItem['score']> = {},
  group: Partial<RecommendationItem['group_accessibility']> = {},
  originCount = 1,
): RecommendationItem {
  return {
    destination: {
      provider_id: id,
      name,
      address: `${name}地址`,
      city: '苏州',
      coordinate: { longitude: 120.7, latitude: 31.3, system: 'gcj02' },
      type_name: '风景名胜',
      type_code: '110000',
      scenery_tags: ['lake'],
      popularity_rank: 1,
      rating: 4.5,
    },
    distances: Array.from({ length: originCount }, (_, index) => ({
      origin_label: index === 0 ? '主出发地' : `同行人 ${index}`,
      distance_km: (group.average_distance_km ?? 10) + index,
      duration_minutes: 20 + index,
      estimated: false,
    })),
    group_accessibility: {
      average_distance_km: group.average_distance_km ?? 10,
      max_distance_km: group.max_distance_km ?? 12,
      distance_variance: group.distance_variance ?? 0,
      distance_stddev: group.distance_stddev ?? 0,
      fairness_score: group.fairness_score ?? 100,
    },
    weather: [{ date: '2026-07-25', condition: '晴', temp_min_c: 20, temp_max_c: 30, precipitation_mm: 0, wind_speed_kmh: 8, humidity_percent: 60, visibility_km: 20, uv_index: 5 }],
    daily_suitability: [{ date: '2026-07-25', score: 80, status: 'suitable', summary: '适合出行', reasons: ['适合'] }],
    score: {
      weather: 80,
      distance: 80,
      fairness: 100,
      popularity: 80,
      coverage_penalty: 0,
      total: 80,
      ...score,
    },
    explanation: `${name}推荐理由`,
    overall_advice: 'suitable',
  }
}

async function checkAll(container: HTMLElement, names: string[]) {
  const user = userEvent.setup()
  for (const name of names) {
    await user.click(within(container).getByRole('checkbox', { name }))
  }
}

describe('CandidateComparison', () => {
  it('does not render comparison controls for fewer than two candidates', () => {
    const { container } = render(<CandidateComparison items={[candidate('a', 'A')]} />)
    expect(container.querySelector('fieldset')).toBeNull()
    expect(container.querySelector('table')).toBeNull()
    expect(screen.queryByRole('checkbox')).toBeNull()
  })

  it('shows named checkboxes inside a named fieldset when two or more candidates exist', () => {
    const { container } = render(<CandidateComparison items={[candidate('a', '甲'), candidate('b', '乙')]} />)

    const group = screen.getByRole('group', { name: '选择候选进行对比' })
    expect(group).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: '甲' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: '乙' })).toBeInTheDocument()
    expect(container.querySelector('fieldset')).not.toBeNull()
  })

  it('hides the comparison table until at least two candidates are selected', () => {
    render(<CandidateComparison items={[candidate('a', '甲'), candidate('b', '乙')]} />)
    expect(screen.queryByRole('table', { name: '候选地点对比' })).toBeNull()
  })

  it('guides first-time users from one selection to the comparison result', async () => {
    const user = userEvent.setup()
    const onViewComparison = vi.fn()
    render(
      <CandidateComparison
        items={[candidate('a', '甲'), candidate('b', '乙'), candidate('c', '丙')]}
        onViewComparison={onViewComparison}
      />,
    )

    expect(screen.getByText('选择 2～3 个候选，比较天气、路程与多人公平性。')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: '甲' }))
    expect(screen.getByText('已选择 1 个，再选 1 个即可生成对比。')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: '乙' }))
    const viewButton = screen.getByRole('button', { name: '查看对比结果（2）' })
    expect(viewButton).toBeInTheDocument()
    await user.click(viewButton)
    expect(onViewComparison).toHaveBeenCalledTimes(1)
  })

  it('renders full comparison table and conclusion after selecting two candidates', async () => {
    const items = [
      candidate('a', '甲', { total: 90, weather: 80, distance: 60, fairness: 100, popularity: 55 }),
      candidate('b', '乙', { total: 70, weather: 40, distance: 30, fairness: 100, popularity: 88 }),
    ]
    const { container } = render(<CandidateComparison items={items} />)
    await checkAll(container, ['甲', '乙'])

    const expected = compareCandidates(items, 1)
    expect(expected).not.toBeNull()

    const table = within(container).getByRole('table', { name: '候选地点对比' })
    expect(within(table).getByRole('columnheader', { name: '甲' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: '乙' })).toBeInTheDocument()

    for (const row of expected!.rows) {
      expect(within(table).getByRole('rowheader', { name: row.label })).toBeInTheDocument()
    }
    for (const conclusion of expected!.conclusions) {
      expect(screen.getByText(conclusion)).toBeInTheDocument()
    }

    const totalRow = within(table).getByRole('rowheader', { name: '综合分' }).closest('tr')!
    expect(within(totalRow).getByText('90')).toBeInTheDocument()
    expect(within(totalRow).getByText('70')).toBeInTheDocument()

    const weatherRow = within(table).getByRole('rowheader', { name: '天气适宜度' }).closest('tr')!
    expect(within(weatherRow).getByText('80')).toBeInTheDocument()
    expect(within(weatherRow).getByText('40')).toBeInTheDocument()
  })

  it('shows distance metrics with km units', async () => {
    const items = [
      candidate('a', '甲', {}, { average_distance_km: 12, max_distance_km: 15 }),
      candidate('b', '乙', {}, { average_distance_km: 8, max_distance_km: 9 }),
    ]
    const { container } = render(<CandidateComparison items={items} />)
    await checkAll(container, ['甲', '乙'])

    const table = within(container).getByRole('table', { name: '候选地点对比' })

    const avgRow = within(table).getByRole('rowheader', { name: '平均路程' }).closest('tr')!
    expect(within(avgRow).getByText(/12\s*km/)).toBeInTheDocument()
    expect(within(avgRow).getByText(/8\s*km/)).toBeInTheDocument()

    const maxRow = within(table).getByRole('rowheader', { name: '最大路程' }).closest('tr')!
    expect(within(maxRow).getByText(/15\s*km/)).toBeInTheDocument()
    expect(within(maxRow).getByText(/9\s*km/)).toBeInTheDocument()
  })

  it('supports comparing three candidates at once', async () => {
    const items = [
      candidate('a', '甲', { total: 85 }),
      candidate('b', '乙', { total: 75 }),
      candidate('c', '丙', { total: 86 }),
    ]
    const { container } = render(<CandidateComparison items={items} />)
    await checkAll(container, ['甲', '乙', '丙'])

    const expected = compareCandidates(items, 1)
    const table = within(container).getByRole('table', { name: '候选地点对比' })
    for (const row of expected!.rows) {
      expect(within(table).getByRole('rowheader', { name: row.label })).toBeInTheDocument()
    }
    expect(within(table).getByRole('columnheader', { name: '丙' })).toBeInTheDocument()
  })

  it('disables unselected candidates once three are already selected', async () => {
    const items = [
      candidate('a', '甲'),
      candidate('b', '乙'),
      candidate('c', '丙'),
      candidate('d', '丁'),
    ]
    const { container } = render(<CandidateComparison items={items} />)
    await checkAll(container, ['甲', '乙', '丙'])

    expect(screen.getByRole('checkbox', { name: '丁' })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: '甲' })).toBeEnabled()
  })

  it('drops selections that are unavailable after candidates are replaced', async () => {
    const initialItems = [
      candidate('a', '甲'),
      candidate('b', '乙'),
      candidate('c', '丙'),
      candidate('d', '丁'),
    ]
    const { container, rerender } = render(<CandidateComparison items={initialItems} />)
    await checkAll(container, ['甲', '乙', '丙'])

    rerender(<CandidateComparison items={[
      candidate('e', '戊'),
      candidate('f', '己'),
      candidate('g', '庚'),
      candidate('h', '辛'),
    ]} />)

    for (const name of ['戊', '己', '庚', '辛']) {
      expect(screen.getByRole('checkbox', { name })).toBeEnabled()
      expect(screen.getByRole('checkbox', { name })).not.toBeChecked()
    }
  })

  it('allows deselecting one candidate and selecting a replacement', async () => {
    const items = [candidate('a', '甲'), candidate('b', '乙'), candidate('c', '丙')]
    const user = userEvent.setup()
    render(<CandidateComparison items={items} />)

    await user.click(screen.getByRole('checkbox', { name: '甲' }))
    await user.click(screen.getByRole('checkbox', { name: '乙' }))
    await user.click(screen.getByRole('checkbox', { name: '甲' }))
    await user.click(screen.getByRole('checkbox', { name: '丙' }))

    expect(screen.getByRole('table', { name: '候选地点对比' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: '甲' })).not.toBeChecked()
  })

  it('renders "暂无" for a null popularity instead of zero', async () => {
    const items = [
      candidate('a', '甲', { popularity: null }),
      candidate('b', '乙', { popularity: 80 }),
    ]
    const { container } = render(<CandidateComparison items={items} />)
    await checkAll(container, ['甲', '乙'])

    const table = within(container).getByRole('table', { name: '候选地点对比' })
    expect(within(table).getByText('暂无')).toBeInTheDocument()
    expect(within(table).queryByText('0')).toBeNull()
  })

  it('marks best metrics with accessible text, not only color', async () => {
    const items = [
      candidate('a', '甲', { total: 90, weather: 90 }),
      candidate('b', '乙', { total: 50, weather: 30 }),
    ]
    const { container } = render(<CandidateComparison items={items} />)
    await checkAll(container, ['甲', '乙'])

    const table = within(container).getByRole('table', { name: '候选地点对比' })
    expect(within(table).getAllByText('最佳').length).toBeGreaterThan(0)
  })

  it('renders conclusions sourced from compareCandidates', async () => {
    const items = [
      candidate('a', '甲', { total: 80, weather: 80 }),
      candidate('b', '乙', { total: 80, weather: 70 }),
    ]
    const { container } = render(<CandidateComparison items={items} />)
    await checkAll(container, ['甲', '乙'])

    const expected = compareCandidates(items, 1)
    expect(expected).not.toBeNull()
    for (const conclusion of expected!.conclusions) {
      expect(screen.getByText(conclusion)).toBeInTheDocument()
    }
  })

  it('derives originCount from actual distances and shows group fairness conclusion', async () => {
    const items = [
      candidate('a', '甲', { total: 90, weather: 70 }, { average_distance_km: 12, max_distance_km: 30, fairness_score: 40 }, 2),
      candidate('b', '乙', { total: 85, weather: 75 }, { average_distance_km: 11, max_distance_km: 13, fairness_score: 92 }, 2),
    ]
    const { container } = render(<CandidateComparison items={items} />)
    await checkAll(container, ['甲', '乙'])

    const expected = compareCandidates(items, 2)
    expect(expected).not.toBeNull()
    for (const conclusion of expected!.conclusions) {
      expect(screen.getByText(conclusion)).toBeInTheDocument()
    }

    const fairnessRow = within(container).getByRole('rowheader', { name: '多人公平性' }).closest('tr')!
    expect(within(fairnessRow).getByText('92')).toBeInTheDocument()
    expect(within(fairnessRow).getByText('40')).toBeInTheDocument()
  })

  it('uses semantic table headers with correct scope', async () => {
    const items = [
      candidate('a', '甲', { total: 90, weather: 80 }),
      candidate('b', '乙', { total: 70, weather: 40 }),
    ]
    const { container } = render(<CandidateComparison items={items} />)
    await checkAll(container, ['甲', '乙'])

    const table = within(container).getByRole('table', { name: '候选地点对比' })

    const colScope = container.querySelectorAll('th[scope="col"]')
    expect(colScope.length).toBeGreaterThan(0)

    const rowScope = container.querySelectorAll('th[scope="row"]')
    expect(rowScope.length).toBeGreaterThan(0)

    const firstColumnHeader = Array.from(colScope).find((el) => el.textContent?.includes('甲'))
    expect(firstColumnHeader).toBeTruthy()
    expect(within(table).getByRole('columnheader', { name: '甲' })).toBeInTheDocument()
  })
})
