import { describe, expect, it, vi } from 'vitest'

import { ApiClient, ApiError } from '../src/api/client'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('ApiClient', () => {
  it('calls fetch without binding the ApiClient instance as this', async () => {
    const fetchMock = vi.fn(function (this: unknown) {
      if (this !== undefined) throw new TypeError('Illegal invocation')
      return Promise.resolve(jsonResponse({ items: [] }))
    }) as unknown as typeof fetch

    const client = new ApiClient(fetchMock)

    await expect(client.get('/recommendations')).resolves.toEqual({ items: [] })
  })

  it('uses the API prefix, cookies, and the in-memory CSRF token', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ user: { username: 'traveler' }, csrf_token: 'csrf-1' }))
      .mockResolvedValueOnce(jsonResponse({ favorites: [] }))
      .mockResolvedValueOnce(jsonResponse({ favorite: { id: 'fav-1' } }))

    const client = new ApiClient(fetchMock)
    await client.login('traveler', 'password123')
    await client.get('/favorites')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/auth/login',
      expect.objectContaining({ credentials: 'include', method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/favorites',
      expect.objectContaining({ credentials: 'include' }),
    )

    await client.post('/favorites', { provider: 'amap' })
    const mutationInit = fetchMock.mock.calls[2][1]
    expect(new Headers(mutationInit?.headers).get('X-CSRF-Token')).toBe('csrf-1')
  })

  it('refreshes CSRF once and retries the original mutation once', async () => {
    const csrfError = {
      error: { code: 'csrf_invalid', message: 'CSRF invalid.', fields: [] },
    }
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ user: { username: 'traveler' }, csrf_token: 'old' }))
      .mockResolvedValueOnce(jsonResponse(csrfError, 403))
      .mockResolvedValueOnce(jsonResponse({ user: { username: 'traveler' }, csrf_token: 'fresh' }))
      .mockResolvedValueOnce(jsonResponse({ favorite: { id: 'fav-1' } }))

    const client = new ApiClient(fetchMock)
    await client.login('traveler', 'password123')
    await client.post('/favorites', { provider: 'amap' })

    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(fetchMock.mock.calls[2][0]).toBe('/api/v1/auth/me')
    expect(new Headers(fetchMock.mock.calls[3][1]?.headers).get('X-CSRF-Token')).toBe('fresh')
  })

  it('parses the stable backend error envelope', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'validation_error',
            message: 'Request validation failed.',
            fields: [{ path: 'main_origin', message: 'Required' }],
          },
        },
        422,
      ),
    )

    const client = new ApiClient(fetchMock)

    await expect(client.post('/recommendations', {})).rejects.toEqual(
      expect.objectContaining<ApiError>({
        code: 'validation_error',
        status: 422,
        fields: [{ path: 'main_origin', message: 'Required' }],
      }),
    )
  })

  it('clears the in-memory session after an ordinary 401 response', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ user: { username: 'traveler' }, csrf_token: 'csrf-1' }))
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'unauthorized', message: 'Unauthorized.', fields: [] } }, 401))
    const client = new ApiClient(fetchMock)

    await client.login('traveler', 'password123')
    await expect(client.get('/favorites')).rejects.toMatchObject({ status: 401 })

    expect(client.authSession).toBeNull()
  })
})
