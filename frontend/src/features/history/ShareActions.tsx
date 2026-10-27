import { Copy, Link2, Unlink } from 'lucide-react'
import { useState } from 'react'

import { apiClient } from '../../api/client'
import type { Share } from '../../api/types'

type ShareActionsProps = {
  historyId: string
  onCreated?: () => void
  onCopied?: () => void
  onStatus?: (message: string) => void
}

export function ShareActions({ historyId, onCreated, onCopied, onStatus }: ShareActionsProps) {
  const [share, setShare] = useState<Share | null>(null)
  const [status, setStatus] = useState('')
  const [pending, setPending] = useState(false)

  function report(message: string) {
    if (onStatus) onStatus(message)
    else setStatus(message)
  }

  async function create() {
    if (pending) return
    setPending(true)
    try {
      const response = await apiClient.post<{ share: Share }>(`/history/${historyId}/share`)
      setShare(response.share)
      report('分享链接已创建。')
      onCreated?.()
    } catch {
      report('创建分享失败。')
    } finally {
      setPending(false)
    }
  }

  async function copy() {
    if (!share) return
    await navigator.clipboard?.writeText(new URL(share.url, window.location.origin).href)
    report('已复制分享链接。')
    onCopied?.()
  }

  async function revoke() {
    if (!share || pending) return
    setPending(true)
    try {
      await apiClient.delete(`/shares/${share.id}`)
      setShare(null)
      report('分享已撤销。')
    } catch {
      report('撤销分享失败。')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="share-actions">
      <div className="share-action-controls">
      {!share ? (
        <button className="icon-text-button" type="button" disabled={pending} onClick={create}>
          <Link2 aria-hidden="true" size={16} />{pending ? '正在创建…' : '创建分享'}
        </button>
      ) : (
        <>
          <button className="icon-text-button" type="button" aria-label="复制分享链接" onClick={copy}>
            <Copy aria-hidden="true" size={16} />复制链接
          </button>
          <button className="icon-text-button" type="button" aria-label="撤销分享" disabled={pending} onClick={revoke}>
            <Unlink aria-hidden="true" size={16} />{pending ? '正在撤销…' : '撤销分享'}
          </button>
        </>
      )}
      </div>
      <small className="share-status" role="status">{status}</small>
    </div>
  )
}
