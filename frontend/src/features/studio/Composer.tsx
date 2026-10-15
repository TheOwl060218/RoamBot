import { useRef, useState, type ReactNode } from 'react'
import { ArrowUp, MessageCircle } from 'lucide-react'

export function Composer({ busy, onSend, focusedPlace, children }: {
  busy: boolean; onSend: (message: string) => void | Promise<void>; focusedPlace?: string; children?: ReactNode
}) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const composing = useRef(false)
  const lock = useRef(false)
  async function send() {
    if (busy || lock.current || composing.current || !text.trim()) return
    const submitted = text
    lock.current = true; setSending(true)
    try { await onSend(submitted.trim()); setText(current => current === submitted ? '' : current) }
    catch { /* Preserve the original message for an explicit retry. */ }
    finally { lock.current = false; setSending(false) }
  }
  return <div className='studio-composer' data-busy={busy || sending}>
    {focusedPlace && <p className='composer-focus'>正在聊：{focusedPlace}</p>}
    <form onSubmit={e => { e.preventDefault(); void send() }}>
      {children ?? <MessageCircle size={20} aria-hidden='true' />}
      <textarea rows={1} data-command-input aria-keyshortcuts='Alt+/' aria-label='继续补充条件' placeholder='说说想去哪，或继续修改条件…' maxLength={2000}
        value={text} onChange={e => setText(e.target.value)}
        onCompositionStart={() => { composing.current = true }} onCompositionEnd={() => { composing.current = false }}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !composing.current && !e.nativeEvent.isComposing) { e.preventDefault(); void send() } }} />
      <button type='submit' aria-label='发送消息' disabled={busy || sending || !text.trim()}><ArrowUp size={20} /></button>
    </form>
  </div>
}
