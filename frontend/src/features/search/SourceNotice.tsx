import type { SourceState } from '../../api/types'

const labels = {
  live: '实时数据',
  cache: '缓存数据',
  demo: '演示数据',
  degraded: '降级结果',
}

export function SourceNotice({ source }: { source: SourceState }) {
  return (
    <div className={`source-notice source-${source.kind}`} role="status">
      <strong>{labels[source.kind]}</strong>
      {source.notices.map((notice) => <span key={notice}>{notice}</span>)}
    </div>
  )
}
