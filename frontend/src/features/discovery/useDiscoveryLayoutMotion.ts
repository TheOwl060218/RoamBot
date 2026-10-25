import { useEffect, useLayoutEffect, useRef } from 'react'

type Position = { node: HTMLElement; box: DOMRect; fontSize: number }

/** Move the existing controls; no cloned inputs, frozen screenshots or request delays. */
export function useDiscoveryLayoutMotion() {
  const workspace = useRef<HTMLDivElement>(null)
  const pending = useRef<Position[]>([])
  const animations = useRef(new Set<Animation>())
  const prepare = () => {
    if (workspace.current?.dataset.landing !== 'true'
      || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    pending.current = Array.from(workspace.current.querySelectorAll<HTMLElement>(
      '[data-discovery-motion], .studio-composer form',
    )).map(node => ({ node, box: node.getBoundingClientRect(), fontSize: parseFloat(getComputedStyle(node).fontSize) }))
  }
  useLayoutEffect(() => {
    if (!pending.current.length) return
    const positions = pending.current
    pending.current = []
    animations.current.forEach(animation => animation.cancel())
    animations.current.clear()
    for (const { node, box, fontSize } of positions) {
      if (!node.isConnected || !node.animate) continue
      const next = node.getBoundingClientRect()
      if (!next.width || !next.height) continue
      const text = node.hasAttribute('data-discovery-motion')
      const scale = text ? fontSize / parseFloat(getComputedStyle(node).fontSize) : 1
      const scaleX = text ? scale : box.width / next.width
      const scaleY = text ? scale : box.height / next.height
      const dx = box.left - next.left, dy = box.top - next.top
      if (Math.abs(dx) + Math.abs(dy) < 1 && Math.abs(scale - 1) < .01) continue
      const animation = node.animate([
        { transform: `translate3d(${dx}px,${dy}px,0) scale(${scaleX},${scaleY})`, transformOrigin: 'top left' },
        { transform: 'none', transformOrigin: 'top left' },
      ], { duration: 620, easing: 'cubic-bezier(.22,.75,.18,1)' })
      animations.current.add(animation)
      void animation.finished.then(() => animations.current.delete(animation), () => animations.current.delete(animation))
    }
  })
  useEffect(() => () => { animations.current.forEach(animation => animation.cancel()) }, [])
  return { workspace, prepare }
}
