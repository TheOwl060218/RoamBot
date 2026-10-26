import { useRef, useState, type ReactNode } from 'react'
import { ArrowUp, MessageCircle, Square } from 'lucide-react'

export function Composer({ busy, onSend, onCancel, focusedPlace, children, initialText = '', placeholder, suggestions }: {
  busy: boolean; onSend: (message: string) => void | Promise<void>; focusedPlace?: string; children?: ReactNode; initialText?: string
  placeholder?: string; suggestions?: readonly string[]; onCancel?: () => void
}) {
  const [text, setText] = useState(initialText)
  const [sending, setSending] = useState(false)
  const composing = useRef(false)
  const lock = useRef(false)
  const input = useRef<HTMLTextAreaElement>(null)
  const cancelable = !!onCancel
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
      <textarea ref={input} rows={1} data-command-input aria-keyshortcuts='Alt+/' aria-label='继续补充条件' placeholder={placeholder ?? '说说想去哪，或继续修改条件…'} maxLength={2000}
        value={text} onChange={e => setText(e.target.value)}
        onCompositionStart={() => { composing.current = true }} onCompositionEnd={() => { composing.current = false }}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !composing.current && !e.nativeEvent.isComposing) { e.preventDefault(); void send() } }} />
      <button className='composer-action' type={cancelable ? 'button' : 'submit'}
        aria-label={cancelable ? '停止查找' : '发送消息'} title={cancelable ? '取消查找' : '发送消息'}
        onClick={cancelable ? onCancel : undefined} disabled={!cancelable && (busy || sending || !text.trim())}>
        {cancelable ? <Square size={14} fill='currentColor' aria-hidden='true' /> : <ArrowUp size={20} aria-hidden='true' />}
      </button>
    </form>
    {!!suggestions?.length && <div className='composer-suggestions' aria-label='出游灵感'>
      {suggestions.map(suggestion => <button type='button' key={suggestion} disabled={busy || sending}
        onClick={() => { setText(suggestion); input.current?.focus() }}>{suggestion}<span aria-hidden='true'> ↗</span></button>)}
    </div>}
  </div>
}
