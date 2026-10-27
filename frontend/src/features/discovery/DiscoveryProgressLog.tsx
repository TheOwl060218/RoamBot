import { useLayoutEffect, useRef } from 'react'

const noLines: string[] = []

export function DiscoveryProgressLog({ lines = noLines }: { lines?: string[] }) {
  const viewport = useRef<HTMLDivElement>(null)
  const following = useRef(true)
  const scrolling = useRef(false)
  const latest = lines.at(-1)

  useLayoutEffect(() => {
    const element = viewport.current
    if (!element || !following.current || !lines.length) return
    const top = Math.max(0, element.scrollHeight - element.clientHeight)
    scrolling.current = top > element.scrollTop + 1
    element.scrollTo({ top, behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
  }, [lines.length, latest])

  function pause() {
    const element = viewport.current
    if (!element || element.scrollHeight <= element.clientHeight + 3) return
    following.current = false
    scrolling.current = false
    element.scrollTo({ top: element.scrollTop, behavior: 'instant' })
  }

  return <div className='discovery-progress-log' ref={viewport} role='log' aria-label='本次查找过程' aria-live='polite'
    tabIndex={0} onWheel={pause} onTouchStart={pause} onPointerDown={pause}
    onKeyDown={event => { if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) pause() }}
    onScroll={() => {
      const element = viewport.current
      if (!element) return
      const bottom = element.scrollHeight - element.scrollTop - element.clientHeight <= 3
      if (scrolling.current) { if (bottom) scrolling.current = false }
      else following.current = bottom
    }}>
    {lines.map((line, index) => <p key={`${index}:${line}`}>{line}</p>)}
  </div>
}
