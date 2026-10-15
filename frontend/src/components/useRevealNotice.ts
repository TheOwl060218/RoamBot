import { useCallback, useEffect, useRef, useState } from 'react'

// Check the beginning of revealed content, not the full height of a long table.
export function isRevealVisible(target: HTMLElement): boolean {
  const box = target.getBoundingClientRect()
  const header = document.querySelector('.shell-header')?.getBoundingClientRect()
  let top = Math.max(0, header && header.top <= 0 ? header.bottom : 0)
  let bottom = window.innerHeight, left = 0, right = window.innerWidth
  for (let parent = target.parentElement; parent; parent = parent.parentElement) {
    const style = window.getComputedStyle(parent), clip = parent.getBoundingClientRect()
    if (/auto|scroll|hidden|clip/.test(style.overflowY || style.overflow)) {
      top = Math.max(top, clip.top); bottom = Math.min(bottom, clip.bottom)
    }
    if (/auto|scroll|hidden|clip/.test(style.overflowX || style.overflow)) {
      left = Math.max(left, clip.left); right = Math.min(right, clip.right)
    }
  }
  return box.width > 0 && box.height > 0 && box.top >= top
    && box.top + Math.min(60, box.height) <= bottom && box.left >= left
    && box.left + Math.min(120, box.width) <= right
}

export type RevealMessage = { message: string; serial: number } | null
export function useRevealNotice() {
  const [notice, setNotice] = useState<RevealMessage>(null)
  const serial = useRef(0)
  const clear = useCallback(() => setNotice(null), [])
  const notify = useCallback((target: HTMLElement | null, message: string) => {
    if (target && !isRevealVisible(target)) setNotice({ message, serial: ++serial.current })
    else setNotice(null)
  }, [])
  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(clear, 2000)
    return () => window.clearTimeout(timer)
  }, [notice, clear])
  return { notice, notify, clear }
}
