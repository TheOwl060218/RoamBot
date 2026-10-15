import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { loadRegionCatalog, normalizeRegions, type RegionCatalog, type Region } from './regions'

export function RegionInput({ value, onChange, query, onQueryChange }: {
  value: string[]; onChange: (value: string[]) => void
  query: string; onQueryChange: (query: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [catalog, setCatalog] = useState<RegionCatalog | null>(null)
  const [failed, setFailed] = useState(false)
  const [active, setActive] = useState(0)
  const [position, setPosition] = useState({ top: 0, left: 12, width: 300, maxHeight: 320 })
  const anchor = useRef<HTMLDivElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const visibleCount = Math.min(2, value.length)
  const composing = useRef(false)
  const alive = useRef(true)
  const listId = useId()
  const rows = catalog?.regions ?? []
  const selected = value.map((code) => rows.find((row) => row.adcode === code)
    ?? { adcode: code, name: '地区信息待确认', level: 'city' as const, province_adcode: '' })
  const candidates = rows.filter((row) => row.name.includes(query.trim()))
  const name = (row: Region) => row.level === 'province' ? row.name
    : `${row.name} · ${rows.find((parent) => parent.adcode === row.province_adcode)?.name ?? '所属省份待确认'}`
  const covered = (row: Region) => row.level === 'city' && value.includes(row.province_adcode)
  const available = candidates.filter((row) => !covered(row))

  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  function load() {
    setFailed(false)
    void loadRegionCatalog().then((next) => { if (alive.current) setCatalog(next) })
      .catch(() => { if (alive.current) setFailed(true) })
  }
  function show() { setOpen(true); if (!catalog) load() }
  useEffect(() => {
    if (!value.length || catalog) return
    let current = true
    void loadRegionCatalog().then((next) => { if (current) setCatalog(next) })
      .catch(() => { if (current) setFailed(true) })
    return () => { current = false }
  }, [value, catalog])
  useEffect(() => {
    if (open && available[active]) document.getElementById(`${listId}-${available[active].adcode}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [open, active, listId, available])
  function choose(row: Region) {
    onChange(normalizeRegions(value.includes(row.adcode)
      ? value.filter((code) => code !== row.adcode) : [...value, row.adcode], catalog!))
    onQueryChange(''); setActive(0); setOpen(false); input.current?.focus()
  }
  useLayoutEffect(() => {
    if (!open) return
    function place() {
      const rect = anchor.current?.getBoundingClientRect()
      if (!rect) return
      const width = Math.min(Math.max(rect.width, 360), document.documentElement.clientWidth - 24)
      const below = window.innerHeight - rect.bottom - 12
      const above = rect.top - 12
      const opensBelow = below >= Math.min(300, above)
      const height = Math.min(420, Math.max(0, (opensBelow ? below : above) - 6))
      setPosition({ left: Math.max(12, Math.min(rect.left, document.documentElement.clientWidth - width - 12)),
        width, maxHeight: height, top: opensBelow ? rect.bottom + 6 : Math.max(12, rect.top - height - 6) })
    }
    place()
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true) }
  }, [open])
  useEffect(() => {
    if (!open) return
    function outside(event: PointerEvent) {
      if (!anchor.current?.contains(event.target as Node) && !panel.current?.contains(event.target as Node)) setOpen(false)
    }
    function escape(event: KeyboardEvent) {
      if (event.key !== 'Escape' || event.defaultPrevented || anchor.current?.closest('[inert]')) return
      // Consume the top popover's Escape before its parent modal sees it.
      event.preventDefault(); event.stopPropagation()
      setOpen(false); input.current?.focus({ preventScroll: true })
    }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape, true)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape, true) }
  }, [open])

  return <div className="region-field">
    <div ref={anchor} className="region-control">
      {selected.slice(0, visibleCount).map((row) => <button type="button" className="region-chip" key={row.adcode}
        title={row.name} aria-label={`移除${row.name}`} onClick={() => onChange(value.filter((code) => code !== row.adcode))}><span>{row.name}</span><span aria-hidden="true">×</span></button>)}
      {selected.length > visibleCount && <button type="button" className="region-chip" aria-label="查看全部已选地区" onClick={show}>+{selected.length - visibleCount}</button>}
      <input ref={input} role="combobox" aria-label="目的地城市范围" aria-expanded={open}
        aria-controls={open ? listId : undefined} aria-autocomplete="list"
        aria-activedescendant={open && available[active] ? `${listId}-${available[active].adcode}` : undefined}
        placeholder={value.length ? '' : '距离内不限省市'} value={query}
        onChange={(event) => { onQueryChange(event.target.value); setActive(0); show() }}
        onCompositionStart={() => { composing.current = true }} onCompositionEnd={() => { composing.current = false }}
        onKeyDown={(event) => {
          if (composing.current || event.nativeEvent.isComposing) return
          if ((event.key === 'Backspace' || event.key === 'Delete') && query === '' && value.length > 0) {
            event.preventDefault()
            onChange(value.slice(0, -1))
          } else if (event.key === 'Enter') {
            event.preventDefault()
            if (open && available[active]) choose(available[active])
          } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault(); show()
            setActive((index) => Math.max(0, Math.min(available.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1))))
          }
        }} />
      <button type="button" className="region-choose" aria-label="选择省市" aria-expanded={open}
        onClick={() => open ? setOpen(false) : show()}>选择</button>
    </div>
    {open && createPortal(<div ref={panel} className="region-popover" role="dialog" aria-label="选择省市" style={{ position: 'fixed', ...position }}>
      <div className="region-popover-heading"><strong>选择省市 · 可多选</strong><button type="button" className="text-button region-reset" onClick={() => { onChange([]); onQueryChange('') }}>恢复不限</button></div>
      {selected.length > 0 && <div className="region-selected">{selected.map((row) => <button type="button" className="region-chip" key={row.adcode}
        aria-label={`取消选择${row.name}`} onClick={() => onChange(value.filter((code) => code !== row.adcode))}>{row.name} ×</button>)}</div>}
      {failed ? <p>地区暂时加载失败。<button type="button" onClick={load}>重试加载地区</button></p> : !catalog ? <p role="status">正在加载地区…</p>
        : <div role="listbox" id={listId} aria-label="省市候选" aria-multiselectable="true">
          {candidates.map((row) => <button type="button" role="option" id={`${listId}-${row.adcode}`} key={row.adcode}
            aria-selected={value.includes(row.adcode) || covered(row)} disabled={covered(row)}
            className={available[active]?.adcode === row.adcode ? 'region-option is-active' : 'region-option'}
            onClick={() => choose(row)}>{name(row)}{covered(row) ? '（已包含在全省中）' : value.includes(row.adcode) ? ' ✓' : ''}</button>)}
          {!candidates.length && <p>没有匹配的省市，请修改输入。</p>}
        </div>}
      <details className="region-footnote">
        <summary>地区信息</summary>
        <p>目录覆盖大陆31个省级地区 · {catalog?.data_date ?? '加载中'} 版本</p>
      </details>
      <button type="button" className="primary-button" onClick={() => { setOpen(false); input.current?.focus() }}>完成选择</button>
    </div>, document.body)}
  </div>
}
