import { createPortal } from 'react-dom'
import { Info } from 'lucide-react'
import type { RevealMessage } from './useRevealNotice'

export function RevealNotice({ notice }: { notice: RevealMessage }) {
  return notice ? createPortal(<div className='plan-feedback-bubble' role='status' aria-atomic='true'>
    <Info size={18} aria-hidden='true' /><span>{notice.message}</span>
  </div>, document.body) : null
}
