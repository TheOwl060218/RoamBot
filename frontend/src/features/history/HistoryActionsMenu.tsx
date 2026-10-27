import { MoreHorizontal, RefreshCcw, Trash2, X } from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'

import { ShareActions } from './ShareActions'
import { trackLayerExit } from '../studio/layerMotion'

type HistoryActionsMenuProps = {
  historyId: string
  rerunning: boolean
  rerunDisabled: boolean
  onRerun: () => void
  onDelete: () => void
  onStatus: (message: string) => void
}

export function HistoryActionsMenu({
  historyId,
  rerunning,
  rerunDisabled,
  onRerun,
  onDelete,
  onStatus,
}: HistoryActionsMenuProps) {
  const [open, setOpen] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const backdropRef = useRef<HTMLButtonElement>(null)
  const [menuPosition, setMenuPosition] = useState({ top: 0, right: 0 })
  const close = useCallback(() => {
    if (open && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      for (const source of [backdropRef.current, popoverRef.current]) {
        if (!source || typeof source.animate !== 'function') continue
        const bounds = source.getBoundingClientRect()
        if (!bounds.width || !bounds.height) continue
        // The live toolbar stays mounted for share state; only a non-interactive
        // face remains visible once it becomes hidden.
        const copy = source.cloneNode(true) as HTMLElement
        const style = getComputedStyle(source)
        Object.assign(copy.style, { position: 'fixed', left: `${bounds.x}px`, top: `${bounds.y}px`, right: 'auto', bottom: 'auto',
          width: `${bounds.width}px`, height: `${bounds.height}px`, margin: '0', transform: 'none', translate: 'none', scale: '1',
          animation: 'none', transition: 'none', opacity: style.opacity, pointerEvents: 'none' })
        copy.dataset.exitSnapshot = 'true'
        copy.setAttribute('aria-hidden', 'true')
        copy.inert = true
        copy.removeAttribute('id')
        copy.querySelectorAll('[id]').forEach(node => node.removeAttribute('id'))
        document.body.append(copy)
        const options = { duration: 280, easing: 'cubic-bezier(.22,.75,.18,1)', fill: 'forwards' as const }
        const fade = copy.animate([{ opacity: style.opacity }, { opacity: 0 }], options)
        const clear = style.backdropFilter && style.backdropFilter !== 'none'
          ? copy.animate([{ backdropFilter: style.backdropFilter }, { backdropFilter: 'blur(0px)' }], options) : null
        trackLayerExit(Promise.allSettled([fade.finished, clear?.finished]).finally(() => copy.remove()))
      }
    }
    setOpen(false)
    setMoreOpen(false)
    triggerRef.current?.focus({ preventScroll: true })
  }, [open])

  useLayoutEffect(() => {
    if (!open) return
    const updatePosition = () => {
      const trigger = triggerRef.current?.getBoundingClientRect()
      if (!trigger) return
      setMenuPosition({
        top: trigger.top + trigger.height / 2,
        right: Math.max(12, window.innerWidth - trigger.right),
      })
    }
    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    popoverRef.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus()

    function closeOnOutsideClick(event: MouseEvent) {
      const target = event.target as Node
      if (!rootRef.current?.contains(target) && !popoverRef.current?.contains(target)) {
        close()
      }
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        close()
      }
    }

    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open, close])

  return (
    <div className="history-actions-menu" ref={rootRef}>
      <button
        className="icon-button history-menu-trigger"
        type="button"
        aria-label="更多历史操作"
        aria-expanded={open}
        tabIndex={open ? -1 : 0}
        style={open ? { opacity: 0 } : undefined}
        ref={triggerRef}
        onClick={() => { setOpen((current) => !current); setMoreOpen(false) }}
      >
        <MoreHorizontal aria-hidden="true" size={18} />
      </button>
      {createPortal(
        <>
          {open && (
            <button
              className="history-menu-backdrop"
              ref={backdropRef}
              type="button"
              aria-label="关闭历史操作"
              onClick={close}
            />
          )}
          <div
            className="history-menu-popover"
            role="toolbar"
            aria-label="历史快捷操作"
            hidden={!open}
            ref={popoverRef}
            onKeyDown={(event) => {
              if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
              const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'))
                .filter((button) => !button.closest('.history-menu-more-panel'))
              const index = buttons.indexOf(document.activeElement as HTMLButtonElement)
              if (index < 0) return
              event.preventDefault()
              const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1
                : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length
              buttons[next]?.focus()
            }}
            style={{
              '--history-menu-top': `${menuPosition.top}px`,
              '--history-menu-right': `${menuPosition.right}px`,
            } as CSSProperties}
          >
            <button
              className="history-menu-action"
              type="button"
              disabled={rerunDisabled}
              onClick={() => {
                close()
                onRerun()
              }}
            >
              <RefreshCcw aria-hidden="true" size={16} />
              {rerunning ? '正在查询…' : '重新查询'}
            </button>
            <ShareActions historyId={historyId} onStatus={onStatus} onCopied={close} />
            <button
              className="history-menu-action"
              type="button"
              aria-expanded={moreOpen}
              onClick={() => setMoreOpen((current) => !current)}
            >
              <MoreHorizontal aria-hidden="true" size={16} />
              更多操作
            </button>
            <button className="history-menu-action history-menu-collapse" type="button" aria-label="收起历史操作" onClick={close}>
              <X aria-hidden="true" size={16} />
            </button>
            {moreOpen && <div className="history-menu-more-panel" role="group" aria-label="其他历史操作">
              <button className="history-menu-action danger" type="button" onClick={() => { close(); onDelete() }}>
                <Trash2 aria-hidden="true" size={16} />删除历史
              </button>
            </div>}
          </div>
        </>,
        document.body,
      )}
    </div>
  )
}
