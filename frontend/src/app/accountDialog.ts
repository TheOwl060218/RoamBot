export const ACCOUNT_DIALOG_REQUEST_EVENT = 'roambot:request-account-dialog'

export function requestAccountDialog(target?: '/plans') {
  window.dispatchEvent(new CustomEvent(ACCOUNT_DIALOG_REQUEST_EVENT, { detail: { target } }))
}
