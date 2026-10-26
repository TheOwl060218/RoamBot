import { useCallback, useEffect, useRef } from 'react'

export function useCoastalMotion() {
  const overlay = useRef<HTMLElement | null>(null)
  const cancel = useCallback(() => { overlay.current?.remove(); overlay.current = null }, [])
  useEffect(() => cancel, [cancel])
  const run = useCallback((source: HTMLElement | null, target: HTMLElement | null, key: string) => {
    cancel()
    if (!source || !target || source === target || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    const from = source.getBoundingClientRect(), visibleTarget = target.getBoundingClientRect()
    // The detail is already playing its entrance transform. Aim at its layout
    // position, not that transient scaled/down-shifted first frame.
    const matrix = typeof DOMMatrix === 'undefined' ? { m11: 1, m22: 1, m41: 0, m42: 0 } : new DOMMatrix(getComputedStyle(target).transform)
    const width = visibleTarget.width / (matrix.m11 || 1)
    const height = visibleTarget.height / (matrix.m22 || 1)
    const to = { width, height,
      left: visibleTarget.left - matrix.m41 - (width - visibleTarget.width) / 2,
      top: visibleTarget.top - matrix.m42 - (height - visibleTarget.height) / 2 }
    if (!from.width || !from.height || !to.width || !to.height || typeof source.animate !== 'function') return
    // Only travel a lightweight face, never duplicate weather lists or map tiles.
    const ghost = source.cloneNode(false) as HTMLElement
    const title = source.querySelector('h2')?.cloneNode(true)
    if (title) ghost.append(title)
    ghost.removeAttribute('role')
    ghost.setAttribute('aria-hidden', 'true')
    ghost.dataset.motionKey = key
    ghost.className = 'coastal-motion-ghost'
    Object.assign(ghost.style, { left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`, height: `${from.height}px` })
    document.body.append(ghost)
    overlay.current = ghost
    const animation = ghost.animate([
      { transform: 'translate3d(0,0,0) scale(1)', opacity: .82, borderRadius: '28px' },
      { transform: `translate3d(${to.left - from.left}px,${to.top - from.top}px,0) scale(${to.width / from.width},${to.height / from.height})`, opacity: 0, borderRadius: '34px' },
    ], { duration: 460, easing: 'cubic-bezier(.22,.75,.18,1)', fill: 'forwards' })
    animation.finished.catch(() => undefined).finally(() => { if (overlay.current === ghost) cancel(); else ghost.remove() })
  }, [cancel])
  return { run, cancel }
}
