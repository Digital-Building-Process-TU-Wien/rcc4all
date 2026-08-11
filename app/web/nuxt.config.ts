import tailwindcss from '@tailwindcss/vite'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
  modules: ['@nuxt/eslint', '@nuxt/fonts', '@nuxt/ui', '@pinia/nuxt'],
  ui: {
    colorMode: false,
    prose: true,
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
      // @ts-expect-error Nuxt’s Vite types are coming from vite/dist/node/index, while @tailwindcss/vite imports from vite
      tailwindcss(),
    ],
  },
})
