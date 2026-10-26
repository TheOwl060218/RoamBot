import { useLayoutEffect, type RefObject } from 'react'

const layers: HTMLElement[] = []
const inertBefore = new Map<HTMLElement, boolean>()
let overflowBefore = ''

function update() {
  const top = layers.at(-1)
  for (const element of Array.from(document.body.children)) {
    if (!(element instanceof HTMLElement)) continue
    if (!inertBefore.has(element)) inertBefore.set(element, element.inert)
    element.inert = top ? element !== top : inertBefore.get(element) ?? false
  }
  if (!top) {
    for (const [element, inert] of inertBefore) element.inert = inert
    inertBefore.clear()
    document.body.style.overflow = overflowBefore
  }
}

/** Nested modals may be removed in either order by browser history. */
export function useModalLayer(root: RefObject<HTMLElement | null>) {
  useLayoutEffect(() => {
    const element = root.current
    if (!element) return
    if (!layers.length) overflowBefore = document.body.style.overflow
    layers.push(element)
    document.body.style.overflow = 'hidden'
    update()
    return () => {
      const index = layers.indexOf(element)
      if (index !== -1) layers.splice(index, 1)
      update()
    }
  }, [root])
}
