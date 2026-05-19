export type SupportedLocale = 'en' | 'de'

export const localeOptions = [
  {
    label: 'EN',
    value: 'en',
  },
  {
    label: 'DE',
    value: 'de',
  },
] as const satisfies { label: string, value: SupportedLocale }[]

export function usei18n() {
  const route = useRoute()
  const currentLocale = useState<SupportedLocale>('content-locale', () => 'en')

  watch(
    () => route.query.locale,
    (locale) => {
      const requestedLocale = Array.isArray(locale) ? locale[0] : locale
      currentLocale.value = isSupportedLocale(requestedLocale) ? requestedLocale : 'en'
    },
    { immediate: true },
  )

  async function changeLocale(nextLocale: SupportedLocale) {
    if (nextLocale === currentLocale.value) {
      return
    }

    currentLocale.value = nextLocale

    await navigateTo(
      {
        query: {
          ...route.query,
          locale: nextLocale,
        },
      },
      {
        replace: true,
      },
    )
  }

  return {
    currentLocale,
    changeLocale,
    localeOptions,
  }
}

function isSupportedLocale(value: unknown): value is SupportedLocale {
  return value === 'en' || value === 'de'
}
