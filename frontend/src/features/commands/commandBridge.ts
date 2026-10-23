export type CommandEffect = { tool: string; arguments: Record<string, unknown> }
export type CommandContext = Record<string, unknown>
type Target = { context: () => CommandContext; handle: (effect: CommandEffect) => boolean | Promise<boolean> }

export function contextFingerprint(context: CommandContext) {
  const turn = context.assistant_turn as { revision?: number } | undefined
  return JSON.stringify([context.page, context.history_id, context.discovery_job_id, context.plan_id, context.invite_token,
    context.result_version, context.focused_id, context.selected_ids, context.layer,
    context.resource_version, context.visible_resources, context.weather_date, context.all_dates,
    context.dirty, turn?.revision])
}

export class CommandBridge {
  private owner: () => string | null
  constructor(owner: () => string | null = () => null) { this.owner = owner }
  private targets = new Map<string, Target>()
  private waiting = new Map<string, Set<() => void>>()
  private previousContexts = new Map<string, { context: CommandContext; owner: string | null }>()
  previousContext(name: string) {
    const saved = this.previousContexts.get(name)
    return saved?.owner === this.owner() ? saved.context : undefined
  }
  clearPreviousContexts() { this.previousContexts.clear() }
  previousResultContext() {
    if (this.targets.has('studio') || this.targets.has('discovery')) return undefined
    const name = [...this.previousContexts.keys()].reverse().find(key => key === 'studio' || key === 'discovery')
    return name ? this.previousContext(name) : undefined
  }
  register(name: string, context: Target['context'], handle: Target['handle']) {
    const target = { context, handle }
    const owner = this.owner()
    this.targets.set(name, target)
    this.waiting.get(name)?.forEach(resolve => resolve())
    return () => {
      if (this.targets.get(name) === target) {
        if (owner === this.owner()) {
          this.previousContexts.delete(name)
          this.previousContexts.set(name, { context: target.context(), owner })
        }
        this.targets.delete(name)
      }
    }
  }
  context() {
    return Object.assign({}, ...[...this.targets.values()].map(target => target.context())) as CommandContext
  }
  whenReady(additionalReady = () => true) {
    if (!this.context().page_loading && additionalReady()) return Promise.resolve()
    return new Promise<void>((resolve, reject) => {
      let frame = 0
      const timer = setTimeout(() => { cancelAnimationFrame(frame); reject(new Error('页面数据还未加载完成，请稍后发送。')) }, 10000)
      const check = () => {
        if (!this.context().page_loading && additionalReady()) { clearTimeout(timer); resolve() }
        else frame = requestAnimationFrame(check)
      }
      frame = requestAnimationFrame(check)
    })
  }
  async dispatch(effect: CommandEffect) {
    for (const target of [...this.targets.values()].reverse()) {
      if (await target.handle(effect)) return true
    }
    return false
  }
  async perform(effect: CommandEffect) {
    if (!await this.dispatch(effect)) throw new Error('当前页面无法执行这个界面动作。')
  }
  waitFor(name: string) {
    if (this.targets.has(name)) return Promise.resolve()
    return new Promise<void>((resolve, reject) => {
      const waiting = this.waiting.get(name) ?? new Set()
      const done = () => { clearTimeout(timer); waiting.delete(done); resolve() }
      const timer = setTimeout(() => { waiting.delete(done); reject(new Error('页面尚未准备好。')) }, 5000)
      waiting.add(done)
      this.waiting.set(name, waiting)
    })
  }
}
