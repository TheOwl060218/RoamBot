import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from 'react'
import { createPortal } from 'react-dom'

type Props = { id: string; title: string; summary: string; anchor: RefObject<HTMLButtonElement | null>; onClose: () => void }

export function DayExplanationPopover({ id, title, summary, anchor, onClose }: Props) {
  const panel = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState<CSSProperties>({ visibility: 'hidden' })
  useLayoutEffect(() => {
    const place = () => {
      if (!anchor.current || !panel.current) return
      const button = anchor.current.getBoundingClientRect()
      const header = document.querySelector('.shell-header')?.getBoundingClientRect()
      const topEdge = Math.max(12, header && header.top <= 0 ? header.bottom + 12 : 12)
      const above = Math.max(0, button.top - topEdge - 10)
      const below = Math.max(0, window.innerHeight - 12 - button.bottom - 10)
      const height = Math.min(panel.current.scrollHeight ? panel.current.scrollHeight + 2 : 150, 320)
      const upwards = above >= height || (below < height && above >= below)
      const maxHeight = Math.min(320, Math.max(1, upwards ? above : below))
      const shownHeight = Math.min(height, maxHeight)
      const width = Math.min(360, window.innerWidth - 24)
      setPosition({ visibility: 'visible', width, maxHeight,
        left: Math.max(12, Math.min(button.left, window.innerWidth - width - 12)),
        top: upwards ? button.top - shownHeight - 10 : button.bottom + 10 })
    }
    place()
    panel.current?.focus({ preventScroll: true })
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true) }
  }, [anchor])
  useEffect(() => {
    const outside = (event: PointerEvent) => {
      const target = event.target as Node
      if (!panel.current?.contains(target) && !anchor.current?.contains(target)) onClose()
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault(); event.stopImmediatePropagation()
      onClose(); anchor.current?.focus({ preventScroll: true })
    }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape, true)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape, true) }
  }, [anchor, onClose])
  return createPortal(<div id={id} ref={panel} className='day-explanation-popover' style={position}
    role='dialog' aria-modal='false' aria-labelledby={`${id}-title`} tabIndex={-1}>
    <strong id={`${id}-title`}>{title}</strong><p>{summary}</p>
  </div>, document.body)
}
