import { describe, expect, it, vi } from 'vitest'
import { api } from '../../src/lib/api'

describe('API client', () => {
  it('returns JSON from a successful response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })))
    await expect(api.tournaments()).resolves.toEqual([])
  })
  it('normalizes backend errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Capacity reached.' }), { status: 409 })))
    await expect(api.tournaments()).rejects.toMatchObject({ status: 409, message: 'Capacity reached.' })
  })
})
