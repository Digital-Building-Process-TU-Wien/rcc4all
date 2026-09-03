<script setup lang="ts">
const { t } = useI18n()

const projects = [
  {
    id: 'zdb-wohnbau-2025',
    title: 'ZDB Wohnbau 2025',
    subline: 'Wien, 4 Bauabschnitte, 18 Fachmodelle',
    updatedAt: 'Heute, 10:42',
  },
  {
    id: 'klinik-west',
    title: 'Klinik West',
    subline: 'Salzburg, Bestand + Neubau, 9 Modelle',
    updatedAt: 'Gestern, 18:10',
  },
  {
    id: 'bahnhof-nord',
    title: 'Bahnhof Nord',
    subline: 'Graz, Ausschreibung, 6 Modelle',
    updatedAt: '05.02.2026',
  },
  {
    id: 'rathaus-sued',
    title: 'Rathaus Sued',
    subline: 'Innsbruck, Sanierung, 12 Modelle',
    updatedAt: '01.02.2026',
  },
  {
    id: 'quartier-donau',
    title: 'Quartier Donau',
    subline: 'Linz, Mixed Use, 14 Modelle',
    updatedAt: '28.01.2026',
  },
  {
    id: 'schule-ost',
    title: 'Schule Ost',
    subline: 'St. Poelten, Wettbewerb, 4 Modelle',
    updatedAt: '20.01.2026',
  },
]
</script>

<template>
  <div class="space-y-12">
    <UCard class="p-8">
      <div class="flex flex-wrap items-start justify-between gap-6">
        <div>
          <p class="text-xs font-semibold uppercase tracking-widest text-slate-400">
            {{ t('projects.projects') }}
          </p>
          <h1 class="mt-3 text-3xl font-semibold text-dark">
            {{ t('projects.title') }}
          </h1>
          <p class="mt-3 max-w-2xl text-sm text-slate-600">
            {{ t('projects.intro') }}
          </p>
        </div>
        <div class="flex flex-wrap gap-3">
          <UButton color="neutral" variant="outline">
            {{ t('projects.filter') }}
          </UButton>
          <UButton color="primary">
            {{ t('projects.newProject') }}
          </UButton>
        </div>
      </div>
    </UCard>

    <section>
      <div class="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <NuxtLink
          v-for="project in projects"
          :key="project.id"
          :to="`/projects/${project.id}`"
          class="group block transition"
        >
          <UCard class="flex h-full flex-col overflow-hidden transition group-hover:shadow-lg">
            <div class="relative h-40 overflow-hidden bg-linear-to-br from-primary-50 via-white to-accent-50">
              <div class="absolute inset-4 rounded-2xl border border-dashed border-slate-300/70 bg-white/70" />
              <div class="absolute bottom-4 left-4 rounded-full bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-slate-500">
                {{ t('projects.placeholderImage') }}
              </div>
            </div>
            <div class="flex flex-1 flex-col gap-3 p-6">
              <div>
                <h2 class="text-xl font-semibold text-dark">
                  {{ project.title }}
                </h2>
                <p class="mt-2 text-sm text-slate-600">
                  {{ project.subline }}
                </p>
              </div>
              <div class="mt-auto flex items-center justify-between text-xs text-slate-500">
                <span>
                  {{ t('projects.lastUpdated') }}: {{ project.updatedAt }}
                </span>
                <span class="font-semibold text-primary-600">
                  {{ t('projects.details') }}
                </span>
              </div>
            </div>
          </UCard>
        </NuxtLink>
      </div>
    </section>
  </div>
</template>
