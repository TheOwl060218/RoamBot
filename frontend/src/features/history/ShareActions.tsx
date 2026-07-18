import { Copy, Link2, Unlink } from 'lucide-react'
import { useState } from 'react'

import { apiClient } from '../../api/client'
import type { Share } from '../../api/types'

export function ShareActions({ historyId }: { historyId: string }) {
  const [share, setShare] = useState<Share | null>(null)
  const [status, setStatus] = useState('')

  async function create() {
    try {
      const response = await apiClient.post<{ share: Share }>(`/history/${historyId}/share`)
      setShare(response.share)
      setStatus('分享链接已创建。')
    } catch {
      setStatus('创建分享失败。')
    }
  }

  async function copy() {
    if (!share) return
    await navigator.clipboard?.writeText(new URL(share.url, window.location.origin).href)
    setStatus('已复制分享链接。')
  }

  async function revoke() {
    if (!share) return
    try {
      await apiClient.delete(`/shares/${share.id}`)
      setShare(null)
      setStatus('分享已撤销。')
    } catch {
      setStatus('撤销分享失败。')
    }
  }

  return (
    <div className="share-actions">
      {!share ? (
        <button className="icon-text-button" type="button" onClick={create}>
          <Link2 aria-hidden="true" size={16} />创建分享
        </button>
      ) : (
        <>
          <button className="icon-button" type="button" aria-label="复制分享链接" onClick={copy}><Copy aria-hidden="true" size={16} /></button>
          <button className="icon-button" type="button" aria-label="撤销分享" onClick={revoke}><Unlink aria-hidden="true" size={16} /></button>
        </>
      )}
      {status && <small role="status">{status}</small>}
    </div>
  )
}
