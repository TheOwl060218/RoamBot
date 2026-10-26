import { useLayoutEffect, useRef } from 'react'
import { projectConditionCards } from './conditionProjection'
import type { StudioState } from './types'
import type { WorkspacePhase } from './useStudioStage'

export function usePuzzleMotion(state: StudioState, phase: WorkspacePhase) {
  const values = useRef(new Map<string, string>())
  const rectangles = useRef(new Map<string, DOMRect>())
  const animations = useRef<Animation[]>([])
  const ghosts = useRef<HTMLElement[]>([])
  const previousPhase = useRef(phase)
  useLayoutEffect(() => {
    const cards = projectConditionCards(state)
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const nodes = Array.from(document.querySelectorAll<HTMLElement>('.studio-query-page [data-condition-id]'))
    if ((phase === 'toResults' || phase === 'toQuery') && !reduced) {
      animations.current.forEach(animation => animation.cancel())
      ghosts.current.forEach(ghost => ghost.remove())
      ghosts.current = []
      const outward = phase === 'toResults'
      const sourcePage = outward ? '.studio-query-page' : '.studio-results-page'
      const targetPage = outward ? '.studio-results-page' : '.studio-query-page'
      const targetLayer = document.querySelector<HTMLElement>(targetPage)
      const matrix = targetLayer ? getComputedStyle(targetLayer).transform : 'none'
      const shift = !matrix || matrix === 'none' || typeof DOMMatrix === 'undefined' ? 0 : new DOMMatrix(matrix).m42
      for (const source of document.querySelectorAll<HTMLElement>(`${sourcePage} [data-condition-id]`)) {
        const target = document.querySelector<HTMLElement>(`${targetPage} [data-condition-id="${source.dataset.conditionId}"]`)
        if (!target || typeof source.animate !== 'function') continue
        const from = source.getBoundingClientRect(), to = target.getBoundingClientRect()
        if (!from.width || !to.width) continue
        if (outward) {
          const ghost = source.cloneNode(true) as HTMLElement
          ghost.className = 'puzzle-travel-ghost'
          ghost.setAttribute('aria-hidden', 'true'); ghost.inert = true
          Object.assign(ghost.style, { position: 'fixed', left: `${from.x}px`, top: `${from.y}px`, width: `${from.width}px`, height: `${from.height}px` })
          document.body.append(ghost); ghosts.current.push(ghost)
          const targetTransform = `translate3d(${to.x - from.x}px,${to.y - shift - from.y}px,0) scale(${to.width / from.width},${to.height / from.height})`
          const animation = ghost.animate([
            { transform: 'translate3d(0,0,0) scale(1)', opacity: 1, offset: 0 },
            { transform: targetTransform, opacity: .92, offset: .82 },
            { transform: targetTransform, opacity: 0, offset: 1 },
          ], { duration: 760, easing: 'cubic-bezier(.25,.8,.2,1)', fill: 'forwards' })
          animations.current.push(animation)
          animation.finished.catch(() => undefined).finally(() => ghost.remove())
        } else {
          // Animate the actual incoming piece: its translation and opacity belong to
          // the query page, so there is no independent fixed copy crossing the results.
          const animation = target.animate([
            { transform: `scale(${from.width / to.width},${from.height / to.height})`, transformOrigin: 'top left' },
            { transform: 'scale(1)', transformOrigin: 'top left' },
          ], { duration: 760, delay: 200, easing: 'cubic-bezier(.25,.8,.2,1)' })
          animations.current.push(animation)
        }
      }
    }
    if (phase === 'query') {
      const composer = document.querySelector('.studio-composer')?.getBoundingClientRect()
      for (const node of nodes) {
        const id = node.dataset.conditionId!, card = cards.find(c => c.id === id)
        if (!card) continue
        const rect = node.getBoundingClientRect(), old = rectangles.current.get(id)
        if (!reduced && previousPhase.current !== 'toQuery' && typeof node.animate === 'function') {
          if (!values.current.has(id) && composer) animations.current.push(node.animate([
            { transform: `translate3d(${composer.x + composer.width / 2 - rect.x - rect.width / 2}px,${composer.y - rect.y}px,0) scale(.38)`, opacity: 0 },
            { transform: 'translate3d(0,0,0) scale(1)', opacity: 1 },
          ], { duration: 650, delay: cards.indexOf(card) * 55, easing: 'cubic-bezier(.2,.8,.2,1)' }))
          else if (old && (old.x !== rect.x || old.y !== rect.y)) animations.current.push(node.animate([
            { transform: `translate3d(${old.x - rect.x}px,${old.y - rect.y}px,0)` }, { transform: 'translate3d(0,0,0)' },
          ], { duration: 360, easing: 'cubic-bezier(.2,.8,.2,1)' }))
          else if (values.current.get(id) !== card.value) animations.current.push(node.animate([
            { opacity: .45, transform: 'scale(.97)' }, { opacity: 1, transform: 'scale(1)' },
          ], { duration: 300 }))
        }
        rectangles.current.set(id, rect)
      }
    }
    values.current = new Map(cards.map(card => [card.id, card.value]))
    for (const id of rectangles.current.keys()) if (!values.current.has(id)) rectangles.current.delete(id)
    animations.current = animations.current.filter(animation => animation.playState === 'running')
    previousPhase.current = phase
  }, [state, phase])
  useLayoutEffect(() => () => { animations.current.forEach(animation => animation.cancel()); ghosts.current.forEach(ghost => ghost.remove()) }, [])
}
