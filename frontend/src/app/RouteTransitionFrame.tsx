import { useContext, useEffect, useLayoutEffect, useRef, type ReactNode } from 'react'
import { useLocation, useNavigationType, UNSAFE_ViewTransitionContext as ViewTransitionContext } from 'react-router-dom'
import { routeMotion } from './routeMotion'

export function RouteTransitionFrame({ children }: { children: ReactNode }) {
  const location = useLocation(), navigation = useNavigationType()
  // This context defaults to false in MemoryRouter as well as browsers without
  // native VT support; the data-router-only hook would reject that environment.
  const { isTransitioning: viewTransition } = useContext(ViewTransitionContext)
  const previous = useRef<string | null>(null)
  const content = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!viewTransition) document.documentElement.removeAttribute('data-home-explore-transition')
  }, [viewTransition])
  useLayoutEffect(() => {
    if (previous.current === location.pathname) return
    const reverse = navigation === 'POP'
    const motion = routeMotion(reverse ? previous.current ?? location.pathname : location.pathname, reverse)
    document.documentElement.style.setProperty('--route-x', motion.x)
    document.documentElement.style.setProperty('--route-y', motion.y)
    content.current?.style.setProperty('--route-x', motion.x)
    content.current?.style.setProperty('--route-y', motion.y)
    document.documentElement.dataset.route = location.pathname.split('/')[1] || 'home'
    previous.current = location.pathname
    // A true route switch owns the frame; don't let detached modal faces from
    // the outgoing route play over the next page or its native VT snapshot.
    document.querySelectorAll<HTMLElement>('[data-exit-snapshot], .coastal-motion-ghost, .puzzle-travel-ghost').forEach(node => {
      node.getAnimations({ subtree: true }).forEach(animation => animation.cancel())
      node.remove()
    })
    if (viewTransition || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || !content.current?.animate) return
    content.current.animate([
      { opacity: 0, transform: `translate3d(${motion.x},${motion.y},0)` },
      { opacity: 1, transform: 'none' },
    ], { duration: location.pathname === '/recommend' ? 620 : 480, easing: 'cubic-bezier(.22,.75,.18,1)' })
    // Finite animations end on their own. Cancelling in effect cleanup would
    // cancel the only entrance during StrictMode's mount replay.
  }, [location.pathname, navigation, viewTransition])
  return <div className='route-transition-frame'>
    <div key={location.pathname} ref={content} className='route-content'>{children}</div>
  </div>
}
