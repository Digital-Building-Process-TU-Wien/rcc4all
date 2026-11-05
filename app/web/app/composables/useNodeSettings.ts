import type { InjectionKey } from 'vue'

export type OpenNodeSettings = (nodeId: string) => void

export const openNodeSettingsKey: InjectionKey<OpenNodeSettings> = Symbol('openNodeSettings')

/**
 * Node components are rendered deep inside Vue Flow, so they ask the page to
 * open the settings panel instead of owning it themselves.
 */
export function useOpenNodeSettings(): OpenNodeSettings | undefined {
  return inject(openNodeSettingsKey)
}
