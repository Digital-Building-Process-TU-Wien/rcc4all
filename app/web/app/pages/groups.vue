<script setup lang="ts">
import type { Group } from 'rcc4all-payload-types'
import { computed, ref, watch } from 'vue'

const sdk = usePayloadSDK()
const user = sdk.user

const groups = ref<Group[]>([])
const activeGroupId = ref<number | null>(null)
const isLoading = ref(false)
const loadError = ref<string | null>(null)

const groupsById = computed(() => {
  const map = new Map<number, Group>()
  for (const group of groups.value) {
    map.set(group.id, group)
  }
  return map
})

const childrenByParentId = computed(() => {
  const map = new Map<number | null, Group[]>()

  for (const group of groups.value) {
    const parentId = getParentId(group)
    const currentChildren = map.get(parentId) ?? []
    currentChildren.push(group)
    map.set(parentId, currentChildren)
  }

  for (const [parentId, children] of map.entries()) {
    map.set(parentId, sortGroups(children))
  }

  return map
})

const rootGroups = computed(() => {
  return childrenByParentId.value.get(null) ?? []
})

const activeGroup = computed(() => {
  if (activeGroupId.value === null) {
    return null
  }
  return groupsById.value.get(activeGroupId.value) ?? null
})

const parentGroup = computed(() => {
  if (!activeGroup.value) {
    return null
  }

  const parentId = getParentId(activeGroup.value)
  if (parentId === null) {
    return null
  }

  return groupsById.value.get(parentId) ?? null
})

const activeSubgroups = computed(() => {
  if (!activeGroup.value) {
    return []
  }
  return childrenByParentId.value.get(activeGroup.value.id) ?? []
})

watch(
  user,
  async (currentUser) => {
    if (!currentUser) {
      groups.value = []
      activeGroupId.value = null
      return
    }
    await loadGroupsFromApi()
  },
  { immediate: true },
)

watch(
  groups,
  (currentGroups) => {
    if (!currentGroups.length) {
      activeGroupId.value = null
      return
    }

    if (activeGroupId.value !== null && groupsById.value.has(activeGroupId.value)) {
      return
    }

    const firstRoot = rootGroups.value[0]
    activeGroupId.value = firstRoot?.id ?? currentGroups[0]?.id ?? null
  },
  { immediate: true },
)

function getParentId(group: Group): number | null {
  if (typeof group.parent === 'number') {
    return group.parent
  }
  if (group.parent && typeof group.parent === 'object') {
    return group.parent.id
  }
  return null
}

function sortGroups(inputGroups: Group[]): Group[] {
  return [...inputGroups].sort((a, b) => {
    return a.title.localeCompare(b.title)
  })
}

async function loadGroupsFromApi() {
  isLoading.value = true
  loadError.value = null
  try {
    const result = await sdk.find({ collection: 'groups' })
    const docs = (result?.docs ?? []) as Group[]
    groups.value = sortGroups(docs)
  }
  catch (error) {
    console.error('Failed to load groups:', error)
    loadError.value = 'Gruppen konnten nicht geladen werden.'
    groups.value = []
  }
  finally {
    isLoading.value = false
  }
}

function selectRootGroup(group: Group) {
  activeGroupId.value = group.id
}

function switchGroup(group: Group) {
  activeGroupId.value = group.id
}

function goToParentGroup() {
  if (!parentGroup.value) {
    return
  }
  activeGroupId.value = parentGroup.value.id
}

function isRootActive(group: Group): boolean {
  return activeGroup.value?.id === group.id
}
</script>

<template>
  <div class="space-y-12">
    <section class="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
      <div class="flex flex-wrap items-start justify-between gap-6">
        <div>
          <p class="text-xs uppercase tracking-widest text-slate-400">
            Gruppen
          </p>
          <h1 class="mt-3 text-3xl font-semibold text-dark">
            Teams und Berechtigungen
          </h1>
          <p class="mt-3 max-w-2xl text-sm text-slate-600">
            Gruppenstruktur wird direkt aus der API geladen und reagiert auf die aktive Auswahl.
          </p>
        </div>
      </div>
    </section>

    <section class="grid gap-6 lg:grid-cols-[18rem_1fr]">
      <article class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <p class="text-xs uppercase tracking-widest text-slate-400">
          Hauptgruppen
        </p>
        <div v-if="isLoading" class="mt-4 text-sm text-slate-500">
          Lade Gruppen...
        </div>
        <div v-else-if="loadError" class="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {{ loadError }}
        </div>
        <div v-else-if="!rootGroups.length" class="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          Keine Hauptgruppen vorhanden.
        </div>
        <div v-else class="mt-4 space-y-2">
          <button
            v-for="group in rootGroups"
            :key="group.id"
            class="w-full rounded-2xl border px-4 py-3 text-left text-sm font-semibold transition"
            :class="isRootActive(group)
              ? 'border-primary-200 bg-primary-50 text-primary-700'
              : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'"
            @click="selectRootGroup(group)"
          >
            {{ group.title }}
          </button>
        </div>
      </article>

      <article class="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-700">
            <button
              v-if="parentGroup"
              class="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-widest text-slate-600 transition hover:border-slate-400"
              @click="goToParentGroup"
            >
              Zurueck
            </button>
            <span class="text-xs uppercase tracking-widest text-slate-400">Aktive Gruppe</span>
            <span class="text-slate-400">/</span>
            <span>{{ activeGroup?.title ?? 'Keine Auswahl' }}</span>
          </div>
        </div>

        <GroupDisplay
          :active-group="activeGroup"
          :subgroups="activeSubgroups"
          @switch-group="switchGroup"
        />
      </article>
    </section>
  </div>
</template>
