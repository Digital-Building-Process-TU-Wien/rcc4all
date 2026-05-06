<script setup lang="ts">
const heroLinks = [
  {
    label: 'Kontakt aufnehmen',
    to: '/account',
  },
  {
    label: 'Engine erkunden',
    to: '/projects',
    color: 'neutral' as const,
    variant: 'subtle' as const,
  },
]

const featureCards = [
  {
    title: 'No-Code-Regelstudio',
    description: 'Pruefungen in Klartext definieren. Platzhaltertext fuer einen visuellen Regel-Editor und Vorlagen fuer gaengige IFC-Standards.',
    icon: 'i-lucide-square-pen',
  },
  {
    title: 'Versionierung mit Linie',
    description: 'Unveraenderliche Versionen mit veroeffentlichtem Master und geerbten Dateilinks, um Wiederholung zu reduzieren.',
    icon: 'i-lucide-git-branch',
  },
  {
    title: 'Berichte mit Nachweis',
    description: 'Strukturierte Ausgaben fuer Audits. Platzhaltertext fuer Exportformate, Priorisierung und Compliance-Notizen.',
    icon: 'i-lucide-file-text',
  },
  {
    title: 'Geschuetzte Governance',
    description: 'Mehrstufige Gruppenrechte, Magic-Link-Onboarding und Service-Tokens fuer automatisierte Validierungsablaeufe.',
    icon: 'i-lucide-shield-check',
  },
]

const workflowSteps = [
  {
    title: '1. Upload und Versionierung',
    description: 'IFC- und Dokument-Sets hochladen. Das System erzeugt automatisch unveraenderliche Versionen und eine Master-Linie.',
  },
  {
    title: '2. Validierung ausfuehren',
    description: 'Pruefungen per API-Trigger starten. Platzhaltertext fuer den Python-Validator und die Service-Token-Integration.',
  },
  {
    title: '3. Ergebnisse teilen',
    description: 'Bericht veroeffentlichen, Stakeholder informieren und jede Entscheidung nachvollziehbar halten.',
  },
]

const partnerLogos = Array.from({ length: 8 }, (_, index) => ({
  title: `Logo ${index + 1}`,
}))

const ctaLinks = [
  {
    label: 'Projektuebersicht oeffnen',
    to: '/projects',
  },
  {
    label: 'Zum Login',
    to: '/login',
    color: 'neutral' as const,
    variant: 'subtle' as const,
  },
]
</script>

<template>
  <UPage>
    <UPageHero
      headline="Forschungsprojekt ZDB TU Wien"
      title="IFC-Modelle nachvollziehbar pruefen."
      description="Eine forschungsgetriebene OpenBIM-Plattform der TU Wien fuer oeffentliche Auftraggeber. Platzhaltertext fuer Mission, Zielgruppe und Nutzen in wenigen klaren Saetzen."
      orientation="horizontal"
      :links="heroLinks"
    >
      <UCard class="bg-elevated">
        <div class="flex items-center justify-between gap-4">
          <p class="text-sm font-semibold text-toned">
            Validierungslauf
          </p>
          <UBadge color="success" variant="soft">
            Live
          </UBadge>
        </div>

        <div class="mt-6 space-y-4">
          <UCard>
            <p class="text-xs uppercase tracking-widest text-muted">
              Regelpaket
            </p>
            <p class="mt-2 text-sm font-semibold text-highlighted">
              Stadt Wien Core v2
            </p>
          </UCard>

          <div class="grid gap-4 sm:grid-cols-2">
            <UCard>
              <p class="text-xs uppercase tracking-widest text-muted">
                Erfolgsquote
              </p>
              <p class="mt-2 text-2xl font-semibold text-highlighted">
                92%
              </p>
            </UCard>
            <UCard>
              <p class="text-xs uppercase tracking-widest text-muted">
                Hinweise
              </p>
              <p class="mt-2 text-2xl font-semibold text-highlighted">
                14
              </p>
            </UCard>
          </div>

          <UCard>
            <p class="text-xs uppercase tracking-widest text-muted">
              Naechster Schritt
            </p>
            <p class="mt-2 text-sm text-toned">
              Platzhaltertext fuer Hinweise zur Behebung und Links.
            </p>
          </UCard>
        </div>
      </UCard>

      <div class="mt-10 grid gap-6 sm:grid-cols-3">
        <div>
          <p class="text-2xl font-semibold text-highlighted">
            100+
          </p>
          <p class="text-sm text-muted">
            IFC-Dateien geprueft
          </p>
        </div>
        <div>
          <p class="text-2xl font-semibold text-highlighted">
            3 Min.
          </p>
          <p class="text-sm text-muted">
            Durchschn. Laufzeit
          </p>
        </div>
        <div>
          <p class="text-2xl font-semibold text-highlighted">
            Open Source
          </p>
          <p class="text-sm text-muted">
            Engine-Code und Regeln
          </p>
        </div>
      </div>
    </UPageHero>

    <UPageSection
      id="features"
      headline="Funktionen"
      title="Eine robuste Engine mit klaren Ergebnissen"
      description="Platzhaltertext, der beschreibt, wie die Plattform strukturierte Pruefungen ueber Partnernetzwerke hinweg unterstuetzt, ohne Komplexitaet zu erhoehen."
    >
      <UPageGrid>
        <UPageCard
          v-for="card in featureCards"
          :key="card.title"
          :title="card.title"
          :description="card.description"
          :icon="card.icon"
        />
      </UPageGrid>
    </UPageSection>

    <UPageSection
      headline="So funktioniert es"
      title="Von Upload bis nachvollziehbarem Ergebnis"
      description="Platzhaltertext, der den Validierungsablauf ueber Abteilungen und Partnernetzwerke hinweg beschreibt."
    >
      <UPageGrid>
        <UPageCard
          v-for="step in workflowSteps"
          :key="step.title"
          :title="step.title"
          :description="step.description"
        />
      </UPageGrid>
    </UPageSection>

    <UPageSection
      headline="Partner"
      title="Zusammenarbeit ueber Europa hinaus"
      description="Platzhaltertext fuer Partnerschaften aus Wien, ganz Oesterreich und europaeischen Forschungskonsortien."
    >
      <UPageGrid>
        <UPageCard
          v-for="logo in partnerLogos"
          :key="logo.title"
          :title="logo.title"
          description="LOGO"
          variant="subtle"
        />
      </UPageGrid>
    </UPageSection>

    <UPageCTA
      title="Von Regeln zu nachvollziehbaren Ergebnissen"
      description="Die naechsten Iterationen koennen API-Daten, echte Projektkennzahlen und Auth-Flows direkt in diese Nuxt-UI-Struktur einspeisen."
      :links="ctaLinks"
    />
  </UPage>
</template>
