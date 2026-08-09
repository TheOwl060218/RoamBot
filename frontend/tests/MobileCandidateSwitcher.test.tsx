import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { RecommendationItem } from '../src/api/types'
import { MobileCandidateSwitcher } from '../src/features/search/MobileCandidateSwitcher'

function candidate(providerId: string, name: string) {
  return {
    destination: { provider_id: providerId, name },
  } as RecommendationItem
}

describe('MobileCandidateSwitcher', () => {
  const items = [
    candidate('first', '第一个地点'),
    candidate('second', '第二个地点'),
    candidate('third', '第三个地点'),
  ]

  it('wraps from the first candidate to the last when moving left', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    const { container } = render(
      <MobileCandidateSwitcher
        items={items}
        selectedId="first"
        visible
        onSelect={onSelect}
        onOpenDrawer={vi.fn()}
      />,
    )

    await user.click(container.querySelectorAll<HTMLButtonElement>('.icon-button')[0])

    expect(onSelect).toHaveBeenCalledWith(items[2])
  })

  it('wraps from the last candidate to the first when moving right', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    const { container } = render(
      <MobileCandidateSwitcher
        items={items}
        selectedId="third"
        visible
        onSelect={onSelect}
        onOpenDrawer={vi.fn()}
      />,
    )

    await user.click(container.querySelectorAll<HTMLButtonElement>('.icon-button')[1])

    expect(onSelect).toHaveBeenCalledWith(items[0])
  })
})
