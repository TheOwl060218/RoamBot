import { DiscoveryProgressLog } from './DiscoveryProgressLog'

/** Decorative only: no timer, simulated progress or extra requests. */
export function DiscoveryWaiting({ active, stage, notes, runId }: { active: boolean; stage: string; notes?: string[]; runId?: string | null }) {
  return <div className='discovery-waiting' data-active={active} aria-hidden={!active} inert={!active}>
    <svg className='discovery-waiting-landscape' viewBox='0 0 560 220' fill='none' stroke='currentColor' strokeWidth='1.3' strokeLinecap='round' strokeLinejoin='round' aria-hidden='true'>
      <g className='discovery-waiting-scene discovery-waiting-coast'>
        <g className='discovery-waiting-horizon'>
          <path className='discovery-wave discovery-wave-front' d='M100 119C157 97 208 141 264 119S373 97 460 119' />
          <path className='discovery-wave discovery-wave-back' d='M149 144C210 131 262 155 320 144S389 137 411 144' />
        </g>
      </g>
      <g className='discovery-waiting-scene discovery-waiting-mountains'>
        <path className='discovery-waiting-horizon' d='M117 151L205 72Q209 68 213 73L279 139 338 90Q342 86 346 90L443 151' />
        <path className='discovery-mountain-light' d='M117 151L205 72Q209 68 213 73L279 139 338 90Q342 86 346 90L443 151' />
      </g>
    </svg>
    <div className='discovery-waiting-copy' data-has-notes={!!notes?.length}>
      <DiscoveryProgressLog key={runId ?? 'starting'} lines={active ? notes : undefined} />
      <p className='discovery-waiting-caption' aria-hidden={!!notes?.length} role={active && !notes?.length ? 'status' : undefined}>{active ? stage : ''}</p>
    </div>
  </div>
}
