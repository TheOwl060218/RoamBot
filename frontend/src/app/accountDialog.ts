export const ACCOUNT_DIALOG_REQUEST_EVENT = 'roambot:request-account-dialog'

export function requestAccountDialog(target?: '/plans', mode: 'login' | 'register' = 'login') {
  window.dispatchEvent(new CustomEvent(ACCOUNT_DIALOG_REQUEST_EVENT, { detail: { target, mode } }))
}
