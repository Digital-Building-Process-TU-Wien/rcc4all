import tailwindcss from '@tailwindcss/vite'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
  modules: ['@nuxt/eslint', '@nuxt/fonts', '@nuxt/ui', '@pinia/nuxt', '@nuxtjs/i18n'],
  ui: {
    colorMode: false,
    prose: true,
  },
  i18n: {
    strategy: 'no_prefix',
    langDir: 'locales',
    defaultLocale: 'en',
    locales: [
      { code: 'en', name: 'English', file: 'en.json' },
      { code: 'de', name: 'Deutsch', file: 'de.json' },
    ],
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'content-locale',
      alwaysRedirect: false,
      redirectOn: 'root',
      fallbackLocale: 'en',
    },
  },
  runtimeConfig: {
    public: {
      payloadUrl: '',
    },
  },
  eslint: {
    config: {
      standalone: false,
    },
  },
  components: [
    {
      path: '~/components',
      pathPrefix: false,
    },
  ],
  devServer: {
    port: 3001,
  },
  vite: {
    plugins: [
      tailwindcss(),
    ],
  },
})
