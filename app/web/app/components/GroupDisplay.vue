<script setup lang="ts">
import type { Group, User } from 'rcc4all-payload-types'
import { computed } from 'vue'

interface Props {
  activeGroup?: Group | null
  subgroups?: Group[]
}

const props = withDefaults(defineProps<Props>(), {
  activeGroup: null,
  subgroups() {
    return []
  },
})

const emit = defineEmits<{
  switchGroup: [group: Group]
}>()

const { t, locale } = useI18n()

const adminLabels = computed(() => {
  return getRelationLabels(props.activeGroup?.admins)
})

const userLabels = computed(() => {
  return getRelationLabels(props.activeGroup?.users)
})

function getRelationLabels(relations: (number | User)[] | null | undefined): string[] {
  if (!relations?.length) {
    return []
  }

  return relations.map((entry) => {
    return resolveUserLabel(entry)
  })
}

function resolveUserLabel(entry: number | User): string {
  if (typeof entry === 'number') {
    return t('groups.userFallback', { id: entry })
  }

  const name = readString(entry, ['name', 'fullName', 'displayName'])
  if (name) {
    return name
  }

  const email = readString(entry, ['email'])
  if (email) {
    return email
  }

  return t('groups.userFallback', { id: entry.id })
}

function readString(value: unknown, keys: string[]): string | null {
  if (!value || typeof value !== 'object') {
    return null
  }

  const record = value as Record<string, unknown>
  for (const key of keys) {
    const candidate = record[key]
    if (typeof candidate === 'string' && candidate.trim().length) {
      return candidate
    }
  }

  return null
}

function switchToGroup(group: Group) {
  emit('switchGroup', group)
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
</script>

<template>
  <div v-if="!activeGroup" class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-600">
    {{ t('groups.noSelectionDetails') }}
  </div>

  <div v-else class="space-y-6">
    <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 class="text-xl font-semibold text-dark">
            {{ activeGroup.title }}
          </h2>
          <p class="mt-2 text-xs uppercase tracking-widest text-slate-400">
            {{ t('groups.activeGroup') }}
          </p>
        </div>
      </div>

      <div class="mt-4 grid gap-3 text-xs text-slate-500 md:grid-cols-2">
        <p>
          {{ t('groups.createdAt') }} <span class="font-semibold text-slate-700">{{ formatDate(activeGroup.createdAt) }}</span>
        </p>
        <p>
          {{ t('groups.updatedAt') }} <span class="font-semibold text-slate-700">{{ formatDate(activeGroup.updatedAt) }}</span>
        </p>
      </div>

      <div class="mt-5">
        <p class="text-xs uppercase tracking-widest text-slate-400">
          {{ t('groups.subgroups') }}
        </p>
        <div v-if="subgroups.length" class="mt-3 flex flex-wrap gap-2">
          <button
            v-for="subgroup in subgroups"
            :key="subgroup.id"
            class="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600 transition hover:border-primary-200 hover:bg-primary-50 hover:text-primary-700"
            @click="switchToGroup(subgroup)"
          >
            {{ subgroup.title }}
          </button>
        </div>
        <p v-else class="mt-3 text-sm text-slate-500">
          {{ t('groups.noSubgroups') }}
        </p>
      </div>
    </div>

    <div class="grid gap-4 md:grid-cols-2">
      <div class="rounded-2xl border border-slate-200 bg-white p-4">
        <p class="text-xs uppercase tracking-widest text-slate-400">
          {{ t('groups.admins') }}
        </p>
        <div v-if="adminLabels.length" class="mt-3 space-y-2">
          <div
            v-for="admin in adminLabels"
            :key="admin"
            class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700"
          >
            {{ admin }}
          </div>
        </div>
        <p v-else class="mt-3 text-sm text-slate-500">
          {{ t('groups.noAdmins') }}
        </p>
      </div>

      <div class="rounded-2xl border border-slate-200 bg-white p-4">
        <p class="text-xs uppercase tracking-widest text-slate-400">
          {{ t('groups.users') }}
        </p>
        <div v-if="userLabels.length" class="mt-3 space-y-2">
          <div
            v-for="member in userLabels"
            :key="member"
            class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700"
          >
            {{ member }}
          </div>
        </div>
        <p v-else class="mt-3 text-sm text-slate-500">
          {{ t('groups.noUsers') }}
        </p>
      </div>
    </div>
  </div>
</template>
