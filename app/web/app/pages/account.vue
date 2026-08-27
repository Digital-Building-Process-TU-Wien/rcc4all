<script setup lang="ts">
const { t } = useI18n()

const form = reactive({
  fullName: '',
  role: '',
  currentEmail: '',
  newEmail: '',
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})
</script>

<template>
  <div class="space-y-12">
    <UCard class="p-8">
      <div class="flex flex-wrap items-start justify-between gap-6">
        <div class="text-left">
          <p class="text-xs font-semibold uppercase tracking-widest text-slate-400">
            {{ t('account.user') }}
          </p>
          <h1 class="mt-3 text-3xl font-semibold text-dark">
            {{ t('account.title') }}
          </h1>
          <p class="mt-3 max-w-2xl text-sm text-slate-600">
            {{ t('account.intro') }}
          </p>
        </div>
        <UButton color="primary">
          {{ t('account.save') }}
        </UButton>
      </div>
    </UCard>

    <section class="grid gap-6 lg:grid-cols-2">
      <UCard>
        <h2 class="text-xl font-semibold text-dark">
          {{ t('account.profile') }}
        </h2>
        <p class="mt-2 text-sm text-slate-600">
          {{ t('account.profileIntro') }}
        </p>
        <div class="mt-6 space-y-4">
          <div class="space-y-2">
            <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-full-name">
              {{ t('account.fullName') }}
            </label>
            <UInput
              id="account-full-name"
              v-model="form.fullName"
              :placeholder="t('account.fullNamePlaceholder')"
            />
          </div>
          <div class="space-y-2">
            <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-role">
              {{ t('account.role') }}
            </label>
            <UInput
              id="account-role"
              v-model="form.role"
              :placeholder="t('account.rolePlaceholder')"
            />
          </div>
        </div>
      </UCard>

      <UCard>
        <h2 class="text-xl font-semibold text-dark">
          {{ t('account.email') }}
        </h2>
        <p class="mt-2 text-sm text-slate-600">
          {{ t('account.emailIntro') }}
        </p>
        <div class="mt-6 space-y-4">
          <div class="space-y-2">
            <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-current-email">
              {{ t('account.currentEmail') }}
            </label>
            <UInput
              id="account-current-email"
              v-model="form.currentEmail"
              type="email"
              placeholder="alexandra@rcc4all.org"
            />
          </div>
          <div class="space-y-2">
            <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-new-email">
              {{ t('account.newEmail') }}
            </label>
            <UInput
              id="account-new-email"
              v-model="form.newEmail"
              type="email"
              placeholder="alexandra@firma.at"
            />
          </div>
          <UButton color="neutral" variant="outline">
            {{ t('account.updateEmail') }}
          </UButton>
        </div>
      </UCard>
    </section>

    <UCard>
      <h2 class="text-xl font-semibold text-dark">
        {{ t('account.password') }}
      </h2>
      <p class="mt-2 text-sm text-slate-600">
        {{ t('account.passwordIntro') }}
      </p>
      <div class="mt-6 grid gap-4 lg:grid-cols-3">
        <div class="space-y-2">
          <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-current-password">
            {{ t('account.currentPassword') }}
          </label>
          <UInput
            id="account-current-password"
            v-model="form.currentPassword"
            type="password"
            placeholder="********"
          />
        </div>
        <div class="space-y-2">
          <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-new-password">
            {{ t('account.newPassword') }}
          </label>
          <UInput
            id="account-new-password"
            v-model="form.newPassword"
            type="password"
            :placeholder="t('account.newPasswordPlaceholder')"
          />
        </div>
        <div class="space-y-2">
          <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-confirm-password">
            {{ t('account.confirmPassword') }}
          </label>
          <UInput
            id="account-confirm-password"
            v-model="form.confirmPassword"
            type="password"
            :placeholder="t('account.confirmPasswordPlaceholder')"
          />
        </div>
      </div>
      <div class="mt-6">
        <UButton color="primary">
          {{ t('account.changePassword') }}
        </UButton>
      </div>
    </UCard>
  </div>
</template>
