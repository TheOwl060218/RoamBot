export function routeMotion(path: string, reverse = false) {
  const sign = reverse ? -1 : 1
  if (path.startsWith('/favorites')) return { x: `${64 * sign}px`, y: '0px' }
  if (path.startsWith('/history')) return { x: `${-64 * sign}px`, y: '0px' }
  if (path.startsWith('/recommend')) return { x: '0px', y: `${26 * sign}svh` }
  return { x: '0px', y: `${48 * sign}px` }
}
