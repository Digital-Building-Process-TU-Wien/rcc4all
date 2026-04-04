import tailwindcss from '@tailwindcss/vite'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
  modules: ['@nuxt/eslint', '@nuxt/fonts'],
  runtimeConfig: {
    public: {
      payloadUrl: 'http://localhost:3000/api',
    },
  },
  eslint: {
    config: {
      standalone: false,
    },
  },
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
