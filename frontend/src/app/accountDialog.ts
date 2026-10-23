export const ACCOUNT_DIALOG_REQUEST_EVENT = 'roambot:request-account-dialog'
export const ACCOUNT_DIALOG_CANCELLED_EVENT = 'roambot:account-dialog-cancelled'

export function requestAccountDialog(target?: '/plans', mode: 'login' | 'register' = 'login') {
  window.dispatchEvent(new CustomEvent(ACCOUNT_DIALOG_REQUEST_EVENT, { detail: { target, mode } }))
}
