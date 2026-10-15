import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useLayerExit } from './useLayerExit'
import { useModalLayer } from './useModalLayer'

/** A modal owns its layer, not the layout beneath it. */
export function OverlayHost({ label, children, accessory, onClose, className = '', panelClassName = '' }: {
  label: string; children: ReactNode; accessory?: ReactNode; onClose: () => void; className?: string; panelClassName?: string
}) {
  const layer = useRef<HTMLDivElement>(null)
  useLayerExit(layer, 'section')
  useModalLayer(layer)
  const panel = useRef<HTMLElement>(null)
  const outside = useRef(false)
  const previous = useRef(document.activeElement as HTMLElement | null)
  useEffect(() => {
    const trigger = previous.current
    if (!panel.current?.contains(document.activeElement)) {
      const first = panel.current?.querySelector<HTMLElement>('input, textarea, select, button, [tabindex="0"]')
      ;(first ?? panel.current)?.focus({ preventScroll: true })
    }
    return () => {
      if (trigger?.isConnected) trigger.focus({ preventScroll: true })
    }
  }, [])
  return createPortal(<div ref={layer} data-testid='overlay-backdrop' className={`studio-overlay-backdrop ${className}`}
    onPointerDown={e => { outside.current = e.target === e.currentTarget }}
    onPointerUp={e => { if (outside.current && e.target === e.currentTarget) onClose(); outside.current = false }}
    onMouseDown={e => { outside.current = e.target === e.currentTarget }}
    onMouseUp={e => { if (outside.current && e.target === e.currentTarget) onClose(); outside.current = false }}
      onKeyDown={e => {
        if (e.defaultPrevented) return
        if (e.key === 'Escape') { e.preventDefault(); onClose() }
        if (e.key !== 'Tab') return
        const nodes = Array.from(layer.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]') ?? []).filter(node => !node.closest('[inert]'))
        const first = nodes[0], last = nodes.at(-1)
        if (!first) { e.preventDefault(); panel.current?.focus() }
        else if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { e.preventDefault(); last?.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
      }}>
    <section ref={panel} tabIndex={-1} role='dialog' aria-modal='true' aria-label={label} className={panelClassName}>{children}</section>
    {accessory}
  </div>, document.body)
}
