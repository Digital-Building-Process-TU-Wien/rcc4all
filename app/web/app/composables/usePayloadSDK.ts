import type { Config, User } from 'rcc4all-payload-types'
import { PayloadSDK } from '@payloadcms/sdk'

const CMS_TIMEOUT = 1000

type LoginArgs = Parameters<PayloadSDK<Config>['login']>[0]
type LoginResult = Awaited<ReturnType<PayloadSDK<Config>['login']>>

function withTimeout<T>(promise: Promise<T>, timeoutMs = CMS_TIMEOUT): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error(`CMS timeout after ${timeoutMs}ms`)), timeoutMs),
    ),
  ])
}

export function usePayloadSDK() {
  const baseURL = useRuntimeConfig().public.payloadUrl
  const sdk = new PayloadSDK<Config>({ baseURL, baseInit: { credentials: 'include' } })
  const user = useState<User | null | undefined>('payload-user', () => undefined)

  async function fetchCurrentUser() {
    try {
      const result = await withTimeout(sdk.me({ collection: 'users' }))
      user.value = result?.user ?? null
    }
    catch {
      user.value = null
    }
  }

  async function login(args: LoginArgs): Promise<LoginResult> {
    try {
      const result = await withTimeout(sdk.login(args))
      user.value = result?.user ?? null
      return result
    }
    catch (error) {
      user.value = null
      throw error
    }
  }

  async function logout() {
    await withTimeout(sdk.request({
      method: 'POST',
      path: '/users/logout',
    }))
    user.value = null
  }

  if (user.value === undefined) {
    fetchCurrentUser()
  }

  const proxy = new Proxy(sdk, {
    get(target, prop) {
      if (prop === 'login')
        return login
      if (prop === 'logout')
        return logout
      if (prop === 'user')
        return user
      const value = Reflect.get(target, prop)
      if (typeof value === 'function') {
        return (...args: any[]) => withTimeout(value.bind(target)(...args))
      }
      return value
    },
  }) as Omit<PayloadSDK<Config>, 'login' | 'logout'> & {
    login: typeof login
    logout: typeof logout
    user: typeof user
  }

  return proxy
}
