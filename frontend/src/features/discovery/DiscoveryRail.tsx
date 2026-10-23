import { useEffect, useRef, useState, type PropsWithChildren } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

export function DiscoveryRail({ children, label = '推荐去处' }: PropsWithChildren<{ label?: string }>) {
  const rail = useRef<HTMLElement>(null)
  const gesture = useRef<{ id: number; x: number; y: number; scroll: number; moved: boolean } | null>(null)
  const suppressClick = useRef(false)
  const [edges, setEdges] = useState({ left: false, right: false })
  const [dragging, setDragging] = useState(false)
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
    {(edges.left || edges.right) && <div className='discovery-rail-controls' aria-label={`${label}翻页`}>
      <button type='button' className='icon-button' aria-label={`${label}向左滑动`} disabled={!edges.left} onClick={() => move(-1)}><ChevronLeft size={18} /></button>
      <button type='button' className='icon-button' aria-label={`${label}向右滑动`} disabled={!edges.right} onClick={() => move(1)}><ChevronRight size={18} /></button>
    </div>}
  </div>
}
