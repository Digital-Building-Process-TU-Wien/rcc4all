import type { Payload, PayloadRequest } from 'payload'
import type { User } from '@/payload-types'

export function reqAsUser(payload: Payload, user?: User | null): PayloadRequest {
  return {
    payload,
    user: user ?? undefined,
  } as PayloadRequest
}

export function isAccessError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const err = error as { name?: string; message?: string }
  return Boolean(
    err.name === 'Forbidden' ||
    err.message?.includes('not allowed') ||
    err.message?.includes('Forbidden') ||
    err.message?.includes('permission'),
  )
}
