import { useEffect, useState } from 'react'

export const BUSINESS_CHANGED = 'roambot.business-changed'
export function useBusinessRevision() {
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const changed = () => setRevision(value => value + 1)
    window.addEventListener(BUSINESS_CHANGED, changed)
    return () => window.removeEventListener(BUSINESS_CHANGED, changed)
  }, [])
  return revision
}
