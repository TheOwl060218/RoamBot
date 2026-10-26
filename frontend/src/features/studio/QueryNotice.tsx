import { useEffect, useState } from 'react'

export function QueryNotice({ message, busy }: { message: string; busy: boolean }) {
  const [visible, setVisible] = useState(true)
  useEffect(() => {
    const timer = setTimeout(() => setVisible(false), 2000)
    return () => clearTimeout(timer)
  }, [])
  return visible ? <div className='studio-query-notice' role={busy ? 'status' : 'alert'}>{message}</div> : null
}
