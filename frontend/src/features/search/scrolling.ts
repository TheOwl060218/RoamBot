const SCROLL_DURATION_MS = 520
const FALLBACK_HEADER_OFFSET_PX = 76
const LANDING_GAP_PX = 16

function getHeaderOffset() {
  const headerHeight = document.querySelector<HTMLElement>('.shell-header')
    ?.getBoundingClientRect().height
  return headerHeight && headerHeight > 0
    ? headerHeight + LANDING_GAP_PX
    : FALLBACK_HEADER_OFFSET_PX
}

export function startSmoothScrollTo(getTarget: () => HTMLElement | null, onComplete?: () => void) {
  let cancelled = false
  let layoutFrame = 0
  let animationFrame = 0

  layoutFrame = window.requestAnimationFrame(() => {
    layoutFrame = window.requestAnimationFrame(() => {
      const target = getTarget()
      if (!target || cancelled) return
      const startY = window.scrollY
      const targetY = Math.max(0, startY + target.getBoundingClientRect().top - getHeaderOffset())
      const distance = targetY - startY
      if (Math.abs(distance) < 1) {
        onComplete?.()
        return
      }
      let startedAt: number | null = null

      const step = (timestamp: number) => {
        if (cancelled) return
        startedAt ??= timestamp
        const progress = Math.min(1, (timestamp - startedAt) / SCROLL_DURATION_MS)
        const eased = progress < 0.5
          ? 4 * progress * progress * progress
          : 1 - Math.pow(-2 * progress + 2, 3) / 2
        window.scrollTo({ top: startY + distance * eased, behavior: 'auto' })
        if (progress < 1) animationFrame = window.requestAnimationFrame(step)
        else onComplete?.()
      }

      animationFrame = window.requestAnimationFrame(step)
    })
  })

  return () => {
    cancelled = true
    if (layoutFrame) window.cancelAnimationFrame(layoutFrame)
    if (animationFrame) window.cancelAnimationFrame(animationFrame)
  }
}
