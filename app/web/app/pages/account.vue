<script setup lang="ts">
import { reactive } from 'vue'

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
            Benutzer
          </p>
          <h1 class="mt-3 text-3xl font-semibold text-dark">
            Konto und Sicherheit
          </h1>
          <p class="mt-3 max-w-2xl text-sm text-slate-600">
            Profil- und Zugangsdaten verwalten. Die Eingaben sind Platzhalter und koennen spaeter mit echten Nutzerdaten belegt werden.
          </p>
        </div>
        <UButton color="primary">
          Speichern
        </UButton>
      </div>
    </UCard>

    <section class="grid gap-6 lg:grid-cols-2">
      <UCard>
        <h2 class="text-xl font-semibold text-dark">
          Profil
        </h2>
        <p class="mt-2 text-sm text-slate-600">
          Name und Rolle fuer die Kommunikation im Projekt.
        </p>
        <div class="mt-6 space-y-4">
          <div class="space-y-2">
            <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-full-name">
              Vollstaendiger Name
            </label>
            <UInput
              id="account-full-name"
              v-model="form.fullName"
              placeholder="Alexandra Muster"
            />
          </div>
          <div class="space-y-2">
            <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-role">
              Rolle
            </label>
            <UInput
              id="account-role"
              v-model="form.role"
              placeholder="Projektleitung, Auftraggeber"
            />
          </div>
        </div>
      </UCard>

      <UCard>
        <h2 class="text-xl font-semibold text-dark">
          E-Mail
        </h2>
        <p class="mt-2 text-sm text-slate-600">
          Adresse fuer Benachrichtigungen und Einladungen.
        </p>
        <div class="mt-6 space-y-4">
          <div class="space-y-2">
            <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-current-email">
              Aktuelle E-Mail
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
              Neue E-Mail
            </label>
            <UInput
              id="account-new-email"
              v-model="form.newEmail"
              type="email"
              placeholder="alexandra@firma.at"
            />
          </div>
          <UButton color="neutral" variant="outline">
            E-Mail aktualisieren
          </UButton>
        </div>
      </UCard>
    </section>

    <UCard>
      <h2 class="text-xl font-semibold text-dark">
        Passwort
      </h2>
      <p class="mt-2 text-sm text-slate-600">
        Fuer einen sicheren Zugang sollte das Passwort regelmaessig erneuert werden.
      </p>
      <div class="mt-6 grid gap-4 lg:grid-cols-3">
        <div class="space-y-2">
          <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-current-password">
            Aktuelles Passwort
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
            Neues Passwort
          </label>
          <UInput
            id="account-new-password"
            v-model="form.newPassword"
            type="password"
            placeholder="Mind. 12 Zeichen"
          />
        </div>
        <div class="space-y-2">
          <label class="text-xs font-semibold uppercase tracking-widest text-slate-500" for="account-confirm-password">
            Wiederholen
          </label>
          <UInput
            id="account-confirm-password"
            v-model="form.confirmPassword"
            type="password"
            placeholder="Passwort bestaetigen"
          />
        </div>
      </div>
      <div class="mt-6">
        <UButton color="primary">
          Passwort aendern
        </UButton>
      </div>
    </UCard>
  </div>
</template>
