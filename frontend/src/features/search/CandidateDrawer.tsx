import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

import type { RecommendationItem } from '../../api/types'
import { CandidateList } from './CandidateList'

type CandidateDrawerProps = {
  open: boolean
  items: RecommendationItem[]
  selectedId: string
  onSelect: (item: RecommendationItem) => void
  onClose: () => void
}

export function CandidateDrawer({ open, items, selectedId, onSelect, onClose }: CandidateDrawerProps) {
  const dialogRef = useRef<HTMLElement>(null)
  const triggerRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return
    triggerRef.current = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialogRef.current?.focus()

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      triggerRef.current?.focus()
    }
  }, [onClose, open])

  if (!open) return null

  function select(item: RecommendationItem) {
    onSelect(item)
    onClose()
  }

  return (
    <div
      className="candidate-drawer-backdrop"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}
    >
      <section
        ref={dialogRef}
        className="candidate-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="candidate-drawer-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">候选地点</p>
            <h2 id="candidate-drawer-title">选择候选地点</h2>
          </div>
          <button className="icon-button" type="button" aria-label="关闭候选列表" onClick={onClose}>
            <X aria-hidden="true" size={19} />
          </button>
        </header>
        <CandidateList items={items} selectedId={selectedId} onSelect={select} />
      </section>
    </div>
  )
}
