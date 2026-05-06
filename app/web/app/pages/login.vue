<script setup lang="ts">
const sdk = usePayloadSDK()
const router = useRouter()
const email = ref('')
const password = ref('')
const isSubmitting = ref(false)
const errorMessage = ref('')

async function handleLogin() {
  if (isSubmitting.value)
    return

  errorMessage.value = ''
  isSubmitting.value = true

  try {
    await sdk.login({
      collection: 'users',
      data: {
        email: email.value,
        password: password.value,
      },
    })
    await router.push('/groups')
  }
  catch (e: any) {
    console.error('Login error:', e)
    errorMessage.value = 'Login fehlgeschlagen. Bitte pruefen Sie Ihre Daten.'
  }
  finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <UCard class="relative overflow-hidden border shadow-xl shadow-slate-200/60">
    <div class="absolute -top-16 -right-16 h-56 w-56 rounded-full bg-accent-100/70 blur-3xl" />
    <div class="relative grid gap-10 p-8 lg:grid-cols-2 lg:p-12">
      <div class="space-y-6">
        <div class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-4 py-1 text-xs uppercase tracking-widest text-slate-500">
          Mitgliederbereich
        </div>
        <h1 class="text-3xl font-semibold leading-relaxed text-dark sm:text-4xl">
          Willkommen zu <br> RCC4ALL.
        </h1>
      </div>

      <UCard class="bg-white">
        <div class="flex items-center justify-between">
          <p class="text-sm font-semibold uppercase tracking-widest text-slate-500">
            Login
          </p>
        </div>

        <form class="mt-6 flex flex-col gap-4" @submit.prevent="handleLogin">
          <div class="space-y-2">
            <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="email">
              E-Mail-Adresse
            </label>
            <UInput
              id="email"
              v-model="email"
              type="email"
              autocomplete="email"
              placeholder="name@organisation.at"
              class="font-normal"
            />
          </div>

          <div class="space-y-2">
            <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="password">
              Passwort
            </label>
            <UInput
              id="password"
              v-model="password"
              type="password"
              autocomplete="current-password"
              placeholder="Passwort eingeben"
            />
          </div>

          <p v-if="errorMessage" class="text-xs font-semibold text-red-600">
            {{ errorMessage }}
          </p>

          <UButton
            type="submit"
            color="primary"
            class="w-full uppercase"
            :disabled="isSubmitting || !email || !password"
          >
            Login
          </UButton>
        </form>
      </UCard>
    </div>
  </UCard>
</template>
