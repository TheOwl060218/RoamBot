const exits = new Set<Promise<unknown>>()

export function trackLayerExit(finished: Promise<unknown>) {
  exits.add(finished)
  void finished.finally(() => exits.delete(finished))
}

/** Defer a page slide until React's layer cleanup and its visual exit settle. */
export function afterLayerExits(run: () => void) {
  let cancelled = false
  const timer = setTimeout(() => {
    const settle = () => {
      if (cancelled) return
      const routeAnimations = document.querySelector('.route-content')?.getAnimations?.().filter(animation => animation.playState === 'running') ?? []
      const nativeRoutes = document.getAnimations?.().filter(animation =>
        animation instanceof CSSAnimation && animation.animationName.startsWith('coastal-route-') && animation.playState === 'running') ?? []
      if (exits.size || routeAnimations.length || nativeRoutes.length) void Promise.allSettled([
        ...exits, ...routeAnimations.map(animation => animation.finished), ...nativeRoutes.map(animation => animation.finished),
      ]).then(settle)
      else run()
    }
    settle()
  }, 0)
  return () => { cancelled = true; clearTimeout(timer) }
}
