import type { createBrowserRouter, RouterSubscriber } from 'react-router-dom'

/** Router POP may reuse a remembered transition for same-path modal entries.
 * Keep delivering the state update, but only real URL changes own page snapshots.
 */
export function coordinateRouteTransitions(router: ReturnType<typeof createBrowserRouter>) {
  const subscribe = router.subscribe.bind(router)
  router.subscribe = listener => subscribe((state, options) => {
    const transition = options.viewTransitionOpts
    const from = transition?.currentLocation, to = transition?.nextLocation
    const samePage = from && to && from.pathname === to.pathname && from.search === to.search && from.hash === to.hash
    const next: Parameters<RouterSubscriber>[1] = samePage ? { ...options, viewTransitionOpts: undefined } : options
    listener(state, next)
  })
  return router
}
