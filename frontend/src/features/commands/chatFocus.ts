/** A keyboard entry point that follows the active modal rather than its backdrop. */
export const FOCUS_CHAT = 'roambot:focus-chat'

export function usable(element: HTMLElement) {
  if (element.closest('[inert], [aria-hidden="true"]')) return false
  const style = getComputedStyle(element)
  return style.display !== 'none' && style.visibility !== 'hidden'
}

export function focusConversation() {
  const confirmation = document.querySelector<HTMLInputElement>('[data-command-confirm]')
  if (confirmation && usable(confirmation)) { confirmation.focus(); return }
  const inputs = [...document.querySelectorAll<HTMLTextAreaElement>('[data-command-input]')]
  const input = inputs.reverse().find(usable)
  if (input) { input.focus({ preventScroll: true }); return }
  window.dispatchEvent(new Event(FOCUS_CHAT))
}
