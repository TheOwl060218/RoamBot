import { useEffect, useId, useRef, type KeyboardEvent } from 'react'

type ConfirmDialogProps = {
  open: boolean
  title: string
  message: string
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({ open, title, message, confirmLabel, onConfirm, onCancel }: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null)
  const titleId = useId()
  const messageId = useId()

  useEffect(() => {
    if (!open) return
    const previousFocus = document.activeElement as HTMLElement | null
    cancelRef.current?.focus()
    return () => previousFocus?.focus()
  }, [open])

  if (!open) return null

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape') {
      event.preventDefault()
      onCancel()
      return
    }
    if (event.key !== 'Tab') return
    const focusable = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled])'),
    )
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onCancel()
    }}>
      <section
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        onKeyDown={handleKeyDown}
      >
        <h2 id={titleId}>{title}</h2>
        <p id={messageId}>{message}</p>
        <div className="confirm-actions">
          <button ref={cancelRef} className="text-button" type="button" onClick={onCancel}>取消</button>
          <button className="danger-button" type="button" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </section>
    </div>
  )
}
