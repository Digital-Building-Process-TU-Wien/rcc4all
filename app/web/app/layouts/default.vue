<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const isScrolled = ref(false)
const sdk = usePayloadSDK()
const user = sdk.user
const greetingName = computed(() => user.value?.email ?? 'User')
function updateHeaderState() {
  isScrolled.value = window.scrollY > 8
}

onMounted(() => {
  updateHeaderState()
  window.addEventListener('scroll', updateHeaderState, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', updateHeaderState)
})
</script>

<template>
  <div class="min-h-screen">
    <header
      class="sticky top-0 z-50 transition duration-300" :class="[
        isScrolled
          ? 'border-b border-slate-200 bg-slate-50/90 shadow-sm shadow-slate-200/40 backdrop-blur'
          : 'border-b border-transparent bg-transparent',
      ]"
    >
      <div class="relative mx-auto flex max-w-6xl items-center gap-6 px-6 py-4">
        <h1 class="text-lg font-semibold tracking-wide text-primary-500">
          OpenBIM Engine
        </h1>
        <nav class="flex flex-1 flex-wrap items-center gap-4 text-xs font-semibold uppercase tracking-widest text-slate-600">
          <NuxtLink
            to="/"
            class="transition hover:text-slate-950"
          >
            Start
          </NuxtLink>
          <NuxtLink
            to="/projects"
            class="transition hover:text-slate-950"
          >
            Projekte
          </NuxtLink>
          <NuxtLink
            to="/groups"
            class="transition hover:text-slate-950"
          >
            Gruppen
          </NuxtLink>
          <NuxtLink
            v-if="user"
            to="/account"
            class="transition hover:text-slate-950"
          >
            Konto
          </NuxtLink>
          <NuxtLink
            v-if="!user"
            to="/login"
            class="text-xs font-semibold uppercase tracking-widest text-slate-600 transition hover:text-slate-950"
          >
            Login
          </NuxtLink>
          <UBadge
            v-if="user"
            color="primary"
            variant="solid"
            class="ml-auto"
          >
            Hello, {{ greetingName }}
          </UBadge>
          <UButton
            v-if="user"
            color="neutral"
            variant="outline"
            @click="sdk.logout()"
          >
            Logout
          </UButton>
        </nav>
      </div>
    </header>
    <main class="mx-auto w-full max-w-6xl px-6 py-10">
      <slot />
    </main>
  </div>
</template>
