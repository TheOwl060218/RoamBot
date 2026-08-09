import type { AuthResponse, ErrorEnvelope, ErrorField } from './types'

type Fetch = typeof fetch
type AuthListener = (session: AuthResponse | null) => void

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly fields: ErrorField[]

  constructor(
    status: number,
    code: string,
    message: string,
    fields: ErrorField[] = [],
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.fields = fields
  }
}

export class ApiClient {
  private readonly fetcher: Fetch
  private readonly baseUrl: string
  private session: AuthResponse | null = null
  private listeners = new Set<AuthListener>()
  private refreshPromise: Promise<AuthResponse> | null = null

  constructor(
    fetcher: Fetch = fetch,
    baseUrl = '/api/v1',
  ) {
    this.fetcher = fetcher
    this.baseUrl = baseUrl
  }

  get authSession() {
    return this.session
  }

  subscribe(listener: AuthListener) {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  get<T>(path: string) {
    return this.request<T>(path, { method: 'GET' })
  }

  post<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  }

  delete(path: string) {
    return this.request<void>(path, { method: 'DELETE' })
  }

  async register(username: string, password: string) {
    const session = await this.post<AuthResponse>('/auth/register', { username, password })
    this.setSession(session)
    return session
  }

  async login(username: string, password: string) {
    const session = await this.post<AuthResponse>('/auth/login', { username, password })
    this.setSession(session)
    return session
  }

  async me() {
    try {
      const session = await this.request<AuthResponse>('/auth/me', { method: 'GET' }, false)
      this.setSession(session)
      return session
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        this.setSession(null)
        return null
      }
      throw error
    }
  }

  async logout() {
    await this.post<void>('/auth/logout')
    this.setSession(null)
  }

  private async request<T>(path: string, init: RequestInit, retryCsrf = true): Promise<T> {
    const headers = new Headers(init.headers)
    if (init.body !== undefined) headers.set('Content-Type', 'application/json')
    if (this.isMutation(init.method) && this.session?.csrf_token) {
      headers.set('X-CSRF-Token', this.session.csrf_token)
    }

    const fetcher = this.fetcher
    const response = await fetcher(`${this.baseUrl}${path}`, {
      ...init,
      credentials: 'include',
      headers,
    })

    if (response.status === 204) return undefined as T
    const payload = await this.readJson(response)
    if (response.ok) return payload as T

    const apiError = this.toApiError(response.status, payload)
    if (response.status === 401) this.setSession(null)
    if (retryCsrf && apiError.code === 'csrf_invalid' && this.isMutation(init.method)) {
      await this.refreshCsrf()
      return this.request<T>(path, init, false)
    }
    throw apiError
  }

  private refreshCsrf() {
    if (!this.refreshPromise) {
      this.refreshPromise = this.request<AuthResponse>('/auth/me', { method: 'GET' }, false)
        .then((session) => {
          this.setSession(session)
          return session
        })
        .catch((error) => {
          if (error instanceof ApiError && error.status === 401) this.setSession(null)
          throw error
        })
        .finally(() => {
          this.refreshPromise = null
        })
    }
    return this.refreshPromise
  }

  private setSession(session: AuthResponse | null) {
    this.session = session
    this.listeners.forEach((listener) => listener(session))
  }

  private isMutation(method?: string) {
    return !['GET', 'HEAD', 'OPTIONS'].includes((method ?? 'GET').toUpperCase())
  }

  private async readJson(response: Response): Promise<unknown> {
    const text = await response.text()
    if (!text) return null
    try {
      return JSON.parse(text)
    } catch {
      throw new ApiError(response.status, 'invalid_response', '服务器返回了无法解析的响应。')
    }
  }

  private toApiError(status: number, payload: unknown) {
    const envelope = payload as Partial<ErrorEnvelope>
    const body = envelope?.error
    if (body && typeof body.code === 'string' && typeof body.message === 'string') {
      return new ApiError(status, body.code, body.message, Array.isArray(body.fields) ? body.fields : [])
    }
    return new ApiError(status, 'request_failed', '请求失败，请稍后重试。')
  }
}

export const apiClient = new ApiClient()
