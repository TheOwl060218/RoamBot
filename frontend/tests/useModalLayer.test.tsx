import { render } from '@testing-library/react'
import { useRef } from 'react'
import { createPortal } from 'react-dom'
import { expect, it } from 'vitest'
import { useModalLayer } from '../src/features/studio/useModalLayer'

function Layer({ name }: { name: string }) {
  const root = useRef<HTMLDivElement>(null)
  useModalLayer(root)
  return createPortal(<div ref={root} data-layer={name} />, document.body)
}
it('keeps the top layer interactive and restores scroll even when the lower layer closes first', () => {
  document.body.style.overflow = 'auto'
  const view = render(<><Layer key='detail' name='detail' /><Layer key='map' name='map' /></>)
  const map = document.querySelector<HTMLElement>('[data-layer=map]')!
  expect(document.querySelector<HTMLElement>('[data-layer=detail]')!.inert).toBe(true)
  expect(map.inert).toBe(false)
  view.rerender(<><Layer key='map' name='map' /></>)
  expect(document.body.style.overflow).toBe('hidden')
  view.unmount()
  expect(document.body.style.overflow).toBe('auto')
  expect(view.container.inert).toBeFalsy()
})
