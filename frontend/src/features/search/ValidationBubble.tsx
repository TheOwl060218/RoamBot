import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

export function ValidationBubble({ messages }: { messages: string[] }) {
  const [visible, setVisible] = useState(true)
  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(false), 2000)
    return () => window.clearTimeout(timer)
  }, [])

  if (!visible) return null
  // Outside the independently scrolling sidebar so the feedback cannot be clipped.
  return createPortal(
    <div className="validation-bubble" role="alert" aria-label="请检查填写内容" aria-atomic="true">
      <span className="validation-bubble-icon" aria-hidden="true">!</span>
      <div><strong>请检查填写内容</strong>
        <ul>{messages.map((message, index) => <li key={index}>{message}</li>)}</ul>
      </div>
    </div>,
    document.body,
  )
}
