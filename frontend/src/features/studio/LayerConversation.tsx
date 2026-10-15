import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from 'react'
import { MessageCircle, X } from 'lucide-react'
import { Composer } from './Composer'

export function LayerConversation({ label, focusedPlace, messages, status, busy, onSend, children }: {
  label: string; focusedPlace: string; messages: readonly { id: string; role: string; content: string }[]
  status: string; busy: boolean; onSend: (message: string) => Promise<void>
  children?: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const [viewport, setViewport] = useState(() => ({ width: document.documentElement.clientWidth || innerWidth, height: innerHeight }))
  const [anchor, setAnchor] = useState(() => ({ x: Math.max(18, (viewport.width - 1200) / 2), y: viewport.height - Math.min(240, Math.max(130, viewport.height * .24)) - 52 }))
  const [dragging, setDragging] = useState(false), [panelHeight, setPanelHeight] = useState(300)
  const drag = useRef<{ id: number; x: number; y: number; originX: number; originY: number; moved: boolean } | null>(null)
  const skipClick = useRef(false)
  const id = useId(), panel = useRef<HTMLDivElement>(null), trigger = useRef<HTMLButtonElement>(null)
  const records = useRef<HTMLElement>(null), follow = useRef(true)
  const panelWidth = Math.min(420, Math.max(200, viewport.width - 88))
  const clamp = (value: number, max: number) => Math.max(12, Math.min(value, Math.max(12, max)))
  const maxX = viewport.width - 64 - (open ? panelWidth + 12 : 0)
  const x = clamp(anchor.x, maxX), y = clamp(anchor.y, viewport.height - 64)
  const panelY = clamp(y + 52 - panelHeight, viewport.height - panelHeight - 12)
  useLayoutEffect(() => {
    const measure = () => { if (panel.current) setPanelHeight(panel.current.offsetHeight) }
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    if (panel.current) observer?.observe(panel.current)
    const resize = () => setViewport({ width: document.documentElement.clientWidth || innerWidth, height: innerHeight })
    window.addEventListener('resize', resize)
    window.visualViewport?.addEventListener('resize', resize)
    return () => { observer?.disconnect(); window.removeEventListener('resize', resize); window.visualViewport?.removeEventListener('resize', resize) }
  }, [])
  function startDrag(event: PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return
    skipClick.current = false
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, originX: x, originY: y, moved: false }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }
  function moveDrag(event: PointerEvent<HTMLButtonElement>) {
    const current = drag.current
    if (!current || current.id !== event.pointerId) return
    const dx = event.clientX - current.x, dy = event.clientY - current.y
    if (!current.moved && Math.hypot(dx, dy) < 6) return
    current.moved = true; setDragging(true)
    setAnchor({ x: clamp(current.originX + dx, maxX), y: clamp(current.originY + dy, viewport.height - 64) })
  }
  function finishDrag(event: PointerEvent<HTMLButtonElement>) {
    if (drag.current?.id !== event.pointerId) return
    skipClick.current = drag.current.moved
    drag.current = null; setDragging(false)
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }
  useEffect(() => { if (open) panel.current?.querySelector('textarea')?.focus({ preventScroll: true }) }, [open])
  useEffect(() => {
    const element = records.current
    if (!open || !element) return
    if (follow.current) element.scrollTop = element.scrollHeight
    element.dataset.scrolled = String(element.scrollTop > 1)
  }, [open, messages, status])
  useEffect(() => {
    if (!open) return
    // Sending disables its button and can leave focus on body. Escape still
    // belongs to the open chat, provided its containing modal is the top layer.
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented || panel.current?.closest('[inert]')) return
      event.preventDefault(); event.stopPropagation(); setOpen(false)
      trigger.current?.focus({ preventScroll: true })
    }
    document.addEventListener('keydown', escape, true)
    return () => document.removeEventListener('keydown', escape, true)
  }, [open])
  function collapse() { setOpen(false); trigger.current?.focus({ preventScroll: true }) }
  return <div className='layer-conversation' data-open={open} data-dragging={dragging}
    style={{ left: x, top: y, '--orb-roll': `${open ? Math.round((x - anchor.x) / 52) * 360 : 0}deg` } as CSSProperties} onKeyDown={event => {
    if (open && event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); collapse() }
  }}>
    <div ref={panel} id={id} className='layer-chat-panel glass-panel' style={{ width: panelWidth, top: panelY - y }} role='region' aria-label={label} aria-hidden={!open} inert={!open}>
      <header><strong>{focusedPlace}</strong><button type='button' className='icon-button' aria-label={`收起${label}`} onClick={collapse}><X size={18} aria-hidden='true' /></button></header>
      <section ref={records} className='layer-chat-messages studio-conversation' aria-label={`${label}记录`} aria-live='polite' onScroll={event => {
        const element = event.currentTarget
        follow.current = element.scrollHeight - element.clientHeight - element.scrollTop < 24
        element.dataset.scrolled = String(element.scrollTop > 1)
      }}>
        {messages.map(message => <p key={message.id} className={message.role}>{message.content}</p>)}
        {status && <p role='status'>{status}</p>}
      </section>
      <Composer busy={busy} onSend={onSend} />
      {children}
    </div>
    <button ref={trigger} className='studio-chat-orb' type='button' aria-label={open ? `收起${label}` : `打开${label}`} aria-expanded={open} aria-controls={id}
      onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={finishDrag} onPointerCancel={finishDrag}
      onKeyDown={event => {
        const move = { ArrowLeft: [-20, 0], ArrowRight: [20, 0], ArrowUp: [0, -20], ArrowDown: [0, 20] }[event.key]
        if (!move) return
        event.preventDefault(); event.stopPropagation(); setAnchor({ x: clamp(x + move[0], maxX), y: clamp(y + move[1], viewport.height - 64) })
      }}
      onClick={() => { if (skipClick.current) { skipClick.current = false; return }; if (open) collapse(); else setOpen(true) }}>
      <MessageCircle size={24} aria-hidden='true' />
    </button>
  </div>
}
