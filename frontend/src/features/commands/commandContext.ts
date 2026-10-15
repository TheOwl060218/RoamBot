import { createContext, useContext, useLayoutEffect, useRef, type ReactNode } from 'react'
import type { CommandBridge, CommandContext, CommandEffect } from './commandBridge'

export type BusinessAssistantValue = {
  bridge: CommandBridge
  send: (message: string) => Promise<void>
  busy: boolean
  chat?: ReactNode
  recallSelection?: (history: string | null, version: number) => string[]
  rememberSelection?: (history: string | null, version: number, ids: string[]) => void
}
export const BusinessAssistantContext = createContext<BusinessAssistantValue | null>(null)
export function useBusinessAssistant() { return useContext(BusinessAssistantContext) }
export function useCommandTarget(name: string, context: () => CommandContext,
  handle: (effect: CommandEffect) => boolean | Promise<boolean>) {
  const runtime = useBusinessAssistant()
  const latest = useRef({ context, handle })
  useLayoutEffect(() => { latest.current = { context, handle } })
  useLayoutEffect(() => runtime?.bridge.register(name, () => latest.current.context(),
    effect => latest.current.handle(effect)), [name, runtime?.bridge])
}
