import { MoreHorizontal, RefreshCcw, Trash2 } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'

import { ShareActions } from './ShareActions'

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
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const [menuPosition, setMenuPosition] = useState({ top: 0, right: 0 })

  useLayoutEffect(() => {
    if (!open) return
    const updatePosition = () => {
      const trigger = triggerRef.current?.getBoundingClientRect()
      if (!trigger) return
      setMenuPosition({
        top: trigger.top + trigger.height / 2,
        right: window.innerWidth - trigger.left + 8,
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

    function closeOnOutsideClick(event: MouseEvent) {
      const target = event.target as Node
      if (!rootRef.current?.contains(target) && !popoverRef.current?.contains(target)) setOpen(false)
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  return (
    <div className="history-actions-menu" ref={rootRef}>
      <button
        className="icon-button history-menu-trigger"
        type="button"
        aria-label="更多历史操作"
        aria-expanded={open}
        ref={triggerRef}
        onClick={() => setOpen((current) => !current)}
      >
        <MoreHorizontal aria-hidden="true" size={18} />
      </button>
      {createPortal(
        <>
          {open && (
            <button
              className="history-menu-backdrop"
              type="button"
              aria-label="关闭历史操作"
              onClick={() => setOpen(false)}
            />
          )}
          <div
            className="history-menu-popover"
            role="menu"
            hidden={!open}
            ref={popoverRef}
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
                setOpen(false)
                onRerun()
              }}
            >
              <RefreshCcw aria-hidden="true" size={16} />
              {rerunning ? '正在查询…' : '重新查询'}
            </button>
            <ShareActions historyId={historyId} onStatus={onStatus} onCreated={() => setOpen(false)} />
            <button
              className="history-menu-action danger"
              type="button"
              aria-label="删除历史"
              onClick={() => {
                setOpen(false)
                onDelete()
              }}
            >
              <Trash2 aria-hidden="true" size={16} />
              删除历史
            </button>
          </div>
        </>,
        document.body,
      )}
    </div>
  )
}
