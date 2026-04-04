<script setup lang="ts">
const project = {
  title: 'ZDB Wohnbau 2025',
  subtitle: 'Projektlinie fuer TU Wien, Paket 03',
  status: 'Aktiv',
}

const versions = [
  {
    id: 'v1-4',
    name: 'Version 1.4',
    date: '12.02.2026',
    note: 'Prueflauf mit korrigierten Kollisionsregeln',
    published: true,
  },
  {
    id: 'v1-3',
    name: 'Version 1.3',
    date: '04.02.2026',
    note: 'Neue TGA-Modelle hinzugefuegt',
    published: false,
  },
  {
    id: 'v1-2',
    name: 'Version 1.2',
    date: '20.01.2026',
    note: 'Statikmodell aktualisiert',
    published: false,
  },
]

const documents = [
  {
    name: 'Projektbeschreibung.pdf',
    size: '2.4 MB',
    updatedAt: '12.02.2026',
  },
  {
    name: 'Vergaberichtlinien.docx',
    size: '840 KB',
    updatedAt: '11.02.2026',
  },
  {
    name: 'Pruefliste.xlsx',
    size: '1.1 MB',
    updatedAt: '10.02.2026',
  },
]

const ifcFiles = [
  {
    name: 'ARC_Kern_A.ifc',
    size: '120 MB',
    updatedAt: '12.02.2026',
  },
  {
    name: 'TGA_HVAC.ifc',
    size: '86 MB',
    updatedAt: '11.02.2026',
  },
  {
    name: 'STR_Stahlbau.ifc',
    size: '64 MB',
    updatedAt: '10.02.2026',
  },
]

const results = [
  {
    id: 'r-01',
    title: 'Raumhoehen',
    status: 'OK',
    detail: 'Alle Raumhoehen entsprechen den Vorgaben.',
    count: 0,
  },
  {
    id: 'r-02',
    title: 'Kollisionspruefung',
    status: 'Warnung',
    detail: '14 Hinweise in den TGA-Schichten.',
    count: 14,
  },
  {
    id: 'r-03',
    title: 'IFC-Schema',
    status: 'Fehler',
    detail: '3 Bauteile ohne GUID.',
    count: 3,
  },
]
</script>

<template>
  <div class="space-y-12">
    <section class="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
      <div class="flex flex-wrap items-start justify-between gap-6">
        <div>
          <p class="text-xs uppercase tracking-widest text-slate-400">
            Projekt
          </p>
          <h1 class="mt-3 text-3xl font-semibold text-dark">
            {{ project.title }}
          </h1>
          <p class="mt-2 text-sm text-slate-600">
            {{ project.subtitle }}
          </p>
        </div>
        <div class="flex items-center gap-3">
          <BaseBadge class="text-teal-300 ">
            {{ project.status }}
          </BaseBadge>
          <BaseButton class="text-light bg-primary">
            Neue Version
          </BaseButton>
        </div>
      </div>
    </section>

    <section class="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p class="text-xs uppercase tracking-widest text-slate-400">
            Versionen
          </p>
          <h2 class="mt-2 text-2xl font-semibold text-dark">
            Versionierung mit Master-Linie
          </h2>
        </div>
        <button class="rounded-full border border-slate-300 bg-white px-5 py-2 text-xs font-semibold uppercase tracking-widest text-slate-600 transition hover:border-slate-400">
          Master wechseln
        </button>
      </div>
      <div class="grid gap-4 lg:grid-cols-3">
        <article
          v-for="version in versions"
          :key="version.id"
          class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold text-dark">
              {{ version.name }}
            </h3>
            <BaseBadge
              v-if="version.published"
              class="text-teal-300"
            >
              Veroeffentlicht
            </BaseBadge>
          </div>
          <p class="mt-3 text-sm text-slate-600">
            {{ version.note }}
          </p>
          <div class="mt-4 flex items-center justify-between text-xs text-slate-500">
            <span>
              {{ version.date }}
            </span>
            <BaseButton class="bg-gray-100 border text-slate-600">
              Als Master setzen
            </BaseButton>
          </div>
        </article>
      </div>
    </section>

    <section class="space-y-4">
      <div>
        <p class="text-xs uppercase tracking-widest text-slate-400">
          Pruef-Ergebnisse
        </p>
        <h2 class="mt-2 text-2xl font-semibold text-dark">
          Status pro Regelpaket
        </h2>
      </div>
      <div class="grid gap-4 lg:grid-cols-3">
        <article
          v-for="result in results"
          :key="result.id"
          class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold text-dark">
              {{ result.title }}
            </h3>
            <span
              class="rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-widest"
            >
              {{ result.status }}
            </span>
          </div>
          <p class="mt-3 text-sm text-slate-600">
            {{ result.detail }}
          </p>
          <p class="mt-4 text-xs text-slate-500">
            Hinweise: {{ result.count }}
          </p>
        </article>
      </div>
    </section>

    <section class="space-y-4">
      <div>
        <p class="text-xs uppercase tracking-widest text-slate-400">
          Dateien
        </p>
        <h2 class="mt-2 text-2xl font-semibold text-dark">
          Dokumente und IFC-Modelle
        </h2>
      </div>
      <div class="space-y-6">
        <div>
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold text-dark">
              Dokumente
            </h3>
            <button class="text-xs font-semibold uppercase tracking-widest text-primary-600">
              Upload
            </button>
          </div>
          <div class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div
              v-for="doc in documents"
              :key="doc.name"
              class="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
            >
              <p class="text-sm font-semibold text-slate-800">
                {{ doc.name }}
              </p>
              <div class="mt-2 flex items-center justify-between text-xs text-slate-500">
                <span>{{ doc.size }}</span>
                <span>{{ doc.updatedAt }}</span>
              </div>
            </div>
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold text-dark">
              IFC-Modelle
            </h3>
            <button class="text-xs font-semibold uppercase tracking-widest text-primary-600">
              Upload
            </button>
          </div>
          <div class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div
              v-for="file in ifcFiles"
              :key="file.name"
              class="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
            >
              <p class="text-sm font-semibold text-slate-800">
                {{ file.name }}
              </p>
              <div class="mt-2 flex items-center justify-between text-xs text-slate-500">
                <span>{{ file.size }}</span>
                <span>{{ file.updatedAt }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
