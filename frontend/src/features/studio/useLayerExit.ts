import { useEffect, useLayoutEffect, useRef, type RefObject } from 'react'
import { trackLayerExit } from './layerMotion'

/** Keep a non-interactive visual face after unmount; never keep the component alive. */
export function useLayerExit(root: RefObject<HTMLElement | null>, panelSelector: string) {
  const captured = useRef<{ node: HTMLElement; panel: HTMLElement; transform: string; veil: string; scroll: [HTMLElement, number, number][] } | null>(null)
  const pathname = useRef(window.location.pathname)
  useLayoutEffect(() => () => {
    const layer = root.current, panel = layer?.querySelector<HTMLElement>(panelSelector)
    if (!layer || !panel || window.location.pathname !== pathname.current || typeof layer.animate !== 'function' || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return
    const copy = layer.cloneNode(true) as HTMLElement
    const bounds = layer.getBoundingClientRect()
    Object.assign(copy.style, { position: 'fixed', left: `${bounds.x}px`, top: `${bounds.y}px`,
      right: 'auto', bottom: 'auto', width: `${bounds.width}px`, height: `${bounds.height}px`, boxSizing: 'border-box' })
    // Portals lose their ancestor theme; scrollbar restoration must not resize the face.
    const theme = getComputedStyle(layer)
    for (const name of Array.from(theme)) if (name.startsWith('--')) copy.style.setProperty(name, theme.getPropertyValue(name))
    copy.dataset.exitSnapshot = 'true'
    copy.setAttribute('aria-hidden', 'true')
    copy.inert = true
    copy.style.pointerEvents = 'none'
    const originals = [layer, ...layer.querySelectorAll<HTMLElement>('*')]
    const copies = [copy, ...copy.querySelectorAll<HTMLElement>('*')]
    copies.forEach((node, index) => {
      node.removeAttribute('id')
      node.removeAttribute('data-detail-id')
      node.removeAttribute('data-candidate-id')
      node.style.animation = 'none'
      node.style.transition = 'none'
      // Freeze an interrupted entrance at its actual face, rather than jumping
      // to the CSS end pose when animation is removed from the clone.
      if (originals[index].getAnimations?.().length) {
        const style = getComputedStyle(originals[index])
        node.style.transform = style.transform
        node.style.opacity = style.opacity
      }
      if (node instanceof HTMLInputElement && (node.type === 'password' || ['current-password', 'new-password'].includes(node.autocomplete))) {
        node.value = ''
        node.removeAttribute('value')
      }
      // Restore scroll after insertion; detached elements cannot retain scroll offsets.
    })
    const face = copy.querySelector<HTMLElement>(panelSelector)!
    const veil = layer.style.backdropFilter || getComputedStyle(layer).backdropFilter || ''
    captured.current = { node: copy, panel: face, veil, scroll: copies.map((node, index) => [node, originals[index].scrollTop, originals[index].scrollLeft]),
      transform: getComputedStyle(panel).transform || 'none' }
  }, [root, panelSelector])
  useEffect(() => {
    const layer = root.current
    return () => {
      // StrictMode's effect replay is not a real removal.
      if (layer?.isConnected || !captured.current) return
      const { node, panel, transform, veil, scroll } = captured.current
      captured.current = null
      document.body.append(node)
      scroll.forEach(([element, top, left]) => { element.scrollTop = top; element.scrollLeft = left })
      const options = { duration: 320, easing: 'cubic-bezier(.22,.75,.18,1)', fill: 'forwards' as const }
      const fade = node.animate([{ opacity: getComputedStyle(node).opacity || '1' }, { opacity: 0 }], options)
      const move = panel.animate([{ transform }, { transform }], options)
      // The veil must dissolve where it stands; translating the whole layer reads as the page sliding in.
      const clear = veil && veil !== 'none'
        ? node.animate([{ backdropFilter: veil }, { backdropFilter: 'blur(0px)' }], options)
        : null
      trackLayerExit(Promise.allSettled([fade.finished, move.finished, clear?.finished].filter(Boolean)).finally(() => node.remove()))
    }
  }, [root])
}
