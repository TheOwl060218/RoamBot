import { useEffect, useRef, useState, type PropsWithChildren, type ReactNode } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

export function DiscoveryRail({ children, label = '推荐去处', actions, resetKey, focusRequest }: PropsWithChildren<{
  label?: string; actions?: ReactNode; resetKey?: string; focusRequest?: { id: string; revision: number }
}>) {
  const rail = useRef<HTMLElement>(null)
  const gesture = useRef<{ id: number; x: number; y: number; scroll: number; moved: boolean } | null>(null)
  const suppressClick = useRef(false)
  const [edges, setEdges] = useState({ left: false, right: false })
  const [dragging, setDragging] = useState(false)
  useEffect(() => { if (rail.current) rail.current.scrollLeft = 0 }, [resetKey])
  useEffect(() => {
    const element = rail.current
    const card = Array.from(element?.children ?? []).find(node => (node as HTMLElement).dataset.placeId === focusRequest?.id) as HTMLElement | undefined
    if (!element || !card) return
    const frame = requestAnimationFrame(() => {
      const behavior = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
      const bounds = element.getBoundingClientRect(), target = card.getBoundingClientRect()
      const left = element.scrollLeft + target.left - bounds.left
      if (element.scrollTo) element.scrollTo({ left, behavior })
      else element.scrollLeft = left
      const browse = element.closest<HTMLElement>('[data-command-scroll]')
      if (browse) {
        const viewport = browse.getBoundingClientRect()
        if (target.top < viewport.top || target.bottom > viewport.bottom)
          browse.scrollTo?.({ top: browse.scrollTop + target.top - viewport.top - 12, behavior })
      }
      card.dataset.mapFocused = 'true'
      card.querySelector<HTMLElement>('.discovery-card-open')?.focus({ preventScroll: true })
    })
    const timer = window.setTimeout(() => { delete card.dataset.mapFocused }, 2200)
    return () => { cancelAnimationFrame(frame); clearTimeout(timer); delete card.dataset.mapFocused }
  }, [focusRequest, resetKey])
  useEffect(() => {
    const element = rail.current
    if (!element) return
    const update = () => {
      const left = element.scrollLeft > 2, right = element.scrollLeft < element.scrollWidth - element.clientWidth - 2
      setEdges(previous => previous.left === left && previous.right === right ? previous : { left, right })
    }
    let frame = 0
    const resized = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(update) }
    const wheel = (event: WheelEvent) => {
      if (event.ctrlKey || event.shiftKey || Math.abs(event.deltaX) >= Math.abs(event.deltaY)) return
      const browse = element.closest<HTMLElement>('[data-command-scroll]')
      if (browse && browse.scrollHeight > browse.clientHeight + 2) {
        const viewport = browse.getBoundingClientRect(), bounds = element.getBoundingClientRect()
        const below = event.deltaY > 0 && bounds.bottom > viewport.bottom + 2
          && browse.scrollTop < browse.scrollHeight - browse.clientHeight - 2
        const above = event.deltaY < 0 && bounds.top < viewport.top - 2 && browse.scrollTop > 2
        if (below || above) return
      }
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element.clientWidth : 1)
      const next = Math.max(0, Math.min(element.scrollWidth - element.clientWidth, element.scrollLeft + delta))
      if (Math.abs(next - element.scrollLeft) < 1) return
      event.preventDefault()
      element.scrollLeft = next
    }
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(resized)
    observer?.observe(element)
    for (const child of element.children) observer?.observe(child)
    update()
    element.addEventListener('scroll', update, { passive: true })
    element.addEventListener('wheel', wheel, { passive: false })
    window.addEventListener('resize', update)
    return () => { observer?.disconnect(); cancelAnimationFrame(frame); element.removeEventListener('scroll', update)
      element.removeEventListener('wheel', wheel); window.removeEventListener('resize', update) }
  }, [children])
  function move(direction: number) {
    const element = rail.current
    if (!element) return
    const width = element.firstElementChild?.getBoundingClientRect().width ?? element.clientWidth
    element.scrollBy({ left: direction * (width + 20),
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
  }
  return <div className='discovery-rail-frame' data-can-left={edges.left} data-can-right={edges.right}>
    <section ref={rail} className='discovery-rail' aria-label={label} tabIndex={0} data-dragging={dragging}
      onKeyDown={event => {
        if (event.target !== event.currentTarget || event.altKey || event.ctrlKey || event.metaKey) return
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
          event.preventDefault(); move(event.key === 'ArrowRight' ? 1 : -1)
        } else if (event.key === 'Home' || event.key === 'End') {
          event.preventDefault(); event.currentTarget.scrollLeft = event.key === 'Home' ? 0 : event.currentTarget.scrollWidth
        }
      }}
      onPointerDown={event => {
        suppressClick.current = false
        if (event.pointerType !== 'mouse' || event.button !== 0 || (event.target as Element).closest('footer, a, input, textarea')) return
        gesture.current = { id: event.pointerId, x: event.clientX, y: event.clientY,
          scroll: event.currentTarget.scrollLeft, moved: false }
      }}
      onPointerMove={event => {
        const active = gesture.current
        if (!active || active.id !== event.pointerId) return
        const distance = event.clientX - active.x
        if (!active.moved) {
          if (Math.abs(distance) < 8 || Math.abs(distance) < Math.abs(event.clientY - active.y)) return
          active.moved = true; suppressClick.current = true; setDragging(true)
          event.currentTarget.setPointerCapture(event.pointerId)
        }
        event.preventDefault(); event.currentTarget.scrollLeft = active.scroll - distance
      }}
      onPointerUp={event => {
        const active = gesture.current
        if (!active || active.id !== event.pointerId) return
        gesture.current = null; setDragging(false)
        if (active.moved && event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
      }}
      onPointerCancel={() => { gesture.current = null; setDragging(false); suppressClick.current = false }}
      onClickCapture={event => {
        if (!suppressClick.current) return
        suppressClick.current = false; event.preventDefault(); event.stopPropagation()
      }}>
      {children}
    </section>
    {(actions || edges.left || edges.right) && <div className='discovery-rail-controls' aria-label={`${label}操作`}>
      {actions && <div className='discovery-explore-actions'>{actions}</div>}
      <div className='discovery-rail-pagination'>
      <button type='button' className='icon-button' aria-label={`${label}向左滑动`} disabled={!edges.left} onClick={() => move(-1)}><ChevronLeft size={18} /></button>
      <button type='button' className='icon-button' aria-label={`${label}向右滑动`} disabled={!edges.right} onClick={() => move(1)}><ChevronRight size={18} /></button>
      </div>
    </div>}
  </div>
}
