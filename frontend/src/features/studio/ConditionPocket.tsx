import { useEffect, useRef, useState, type ReactNode } from 'react'

export function ConditionPocket({ children }: { children: ReactNode }) {
  const pocket = useRef<HTMLDivElement>(null)
  const [edges, setEdges] = useState({ top: false, bottom: false })
  useEffect(() => {
    const node = pocket.current
    if (!node) return
    const measure = () => setEdges({ top: node.scrollTop > 2, bottom: node.scrollHeight - node.clientHeight - node.scrollTop > 2 })
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    observer?.observe(node)
    if (node.firstElementChild) observer?.observe(node.firstElementChild)
    window.addEventListener('resize', measure)
    node.addEventListener('scroll', measure, { passive: true })
    measure()
    return () => { observer?.disconnect(); node.removeEventListener('scroll', measure); window.removeEventListener('resize', measure) }
  }, [children])
  return <div className={`condition-pocket ${edges.top ? 'has-top' : ''} ${edges.bottom ? 'has-bottom' : ''}`}>
    <div ref={pocket} className='condition-pocket-scroll' aria-label='已理解的条件' tabIndex={0}>{children}</div>
    {edges.bottom && <small className='condition-pocket-hint'>向下查看其他条件 ↓</small>}
  </div>
}
