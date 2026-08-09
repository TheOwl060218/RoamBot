export const ACCOUNT_DIALOG_REQUEST_EVENT = 'roambot:request-account-dialog'

export function requestAccountDialog() {
  window.dispatchEvent(new Event(ACCOUNT_DIALOG_REQUEST_EVENT))
}
