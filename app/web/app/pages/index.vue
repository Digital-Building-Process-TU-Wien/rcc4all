<template>
  <main class="font-sans">
    <section class="relative overflow-hidden bg-linear-to-b from-white via-slate-50 to-slate-100">
      <div class="absolute -top-16 -right-16 h-56 w-56 rounded-full bg-accent-100/70 blur-3xl" />

      <div class="relative mx-auto max-w-6xl px-6 pb-16 pt-20">
        <div class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/70 px-4 py-1 text-xs uppercase tracking-widest text-slate-500">
          Forschungsprojekt ZDB TU Wien
        </div>

        <div class="mt-6 grid gap-12 lg:grid-cols-2 lg:items-center">
          <div>
            <h1 class="text-4xl font-semibold leading-tight text-dark sm:text-5xl">
              IFC-Modelle nachvollziehbar prüfen.
            </h1>
            <p class="mt-4 max-w-2xl text-lg text-slate-600">
              Eine forschungsgetriebene OpenBIM-Plattform der TU Wien, für öffentliche
              Auftraggeber. Platzhaltertext für Mission, Zielgruppe und Nutzen in wenigen klaren
              Sätzen.
            </p>
            <div class="mt-8 flex flex-wrap gap-4">
              <NuxtLink to="/account">
                <BaseButton class="bg-primary text-light uppercase">
                  Kontakt aufnehmen
                </BaseButton>
              </NuxtLink>
              <NuxtLink to="/projects">
                <BaseButton class="bg-white text-dark">
                  Engine erkunden
                </BaseButton>
              </NuxtLink>
            </div>
            <div class="mt-10 grid gap-6 sm:grid-cols-3">
              <div>
                <p class="text-2xl font-semibold text-dark">
                  100+
                </p>
                <p class="text-sm text-slate-500">
                  IFC-Dateien geprüft
                </p>
              </div>
              <div>
                <p class="text-2xl font-semibold text-dark">
                  3 Min.
                </p>
                <p class="text-sm text-slate-500">
                  Durchschn. Laufzeit
                </p>
              </div>
              <div>
                <p class="text-2xl font-semibold text-dark">
                  Open Source
                </p>
                <p class="text-sm text-slate-500">
                  Engine-Code und Regeln
                </p>
              </div>
            </div>
          </div>

          <div class="rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-xl shadow-slate-200/60">
            <div class="flex items-center justify-between">
              <p class="text-sm font-semibold text-slate-700">
                Validierungslauf
              </p>
              <span class="inline-flex items-center gap-2 rounded-full bg-accent-100 px-3 py-1 text-xs font-semibold text-accent-800">
                <span class="h-2 w-2 animate-pulse rounded-full bg-emerald-500" aria-hidden="true" />
                Live
              </span>
            </div>
            <div class="mt-6 space-y-4">
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p class="text-xs uppercase tracking-widest text-slate-400">
                  Regelpaket
                </p>
                <p class="mt-2 text-sm font-semibold text-slate-700">
                  Stadt Wien Core v2
                </p>
              </div>
              <div class="grid gap-4 sm:grid-cols-2">
                <div class="rounded-2xl border border-slate-200 p-4">
                  <p class="text-xs uppercase tracking-widest text-slate-400">
                    Erfolgsquote
                  </p>
                  <p class="mt-2 text-2xl font-semibold text-dark">
                    92%
                  </p>
                </div>
                <div class="rounded-2xl border border-slate-200 p-4">
                  <p class="text-xs uppercase tracking-widest text-slate-400">
                    Hinweise
                  </p>
                  <p class="mt-2 text-2xl font-semibold text-dark">
                    14
                  </p>
                </div>
              </div>
              <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p class="text-xs uppercase tracking-widest text-slate-400">
                  Nächster Schritt
                </p>
                <p class="mt-2 text-sm text-slate-600">
                  Platzhaltertext für Hinweise zur Behebung und Links.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="mx-auto max-w-6xl px-6 py-20">
      <div class="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p class="text-xs uppercase tracking-widest text-slate-400">
            Funktionen
          </p>
          <h2 class="mt-3 text-3xl font-semibold text-dark">
            Eine robuste Engine mit klaren Ergebnissen
          </h2>
        </div>
        <p class="max-w-md text-sm text-slate-500">
          Platzhaltertext, der beschreibt, wie die Plattform strukturierte Prüfungen über
          Partnernetzwerke hinweg unterstützt, ohne Komplexität zu erhöhen.
        </p>
      </div>

      <div class="mt-10 grid gap-6 md:grid-cols-2">
        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 class="text-xl font-semibold text-slate-800">
            No-Code-Regelstudio
          </h3>
          <p class="mt-3 text-sm text-slate-600">
            Prüfungen in Klartext definieren. Platzhaltertext für einen visuellen Regel-Editor
            und Vorlagen für gängige IFC-Standards.
          </p>
        </div>
        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 class="text-xl font-semibold text-slate-800">
            Versionierung mit Linie
          </h3>
          <p class="mt-3 text-sm text-slate-600">
            Unveränderliche Versionen mit veröffentlichtem Master und geerbten Dateilinks, um
            Wiederholung zu reduzieren.
          </p>
        </div>
        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 class="text-xl font-semibold text-slate-800">
            Berichte mit Nachweis
          </h3>
          <p class="mt-3 text-sm text-slate-600">
            Strukturierte Ausgaben für Audits. Platzhaltertext für Exportformate, Priorisierung
            und Compliance-Notizen.
          </p>
        </div>
        <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 class="text-xl font-semibold text-slate-800">
            Geschützte Governance
          </h3>
          <p class="mt-3 text-sm text-slate-600">
            Mehrstufige Gruppenrechte, Magic-Link-Onboarding und Service-Tokens für automatisierte
            Validierungsabläufe.
          </p>
        </div>
      </div>
    </section>

    <section class="bg-white">
      <div class="mx-auto max-w-6xl px-6 py-20">
        <div class="grid gap-10 lg:grid-cols-2">
          <div>
            <p class="text-xs uppercase tracking-widest text-slate-400">
              So funktioniert es
            </p>
            <h2 class="mt-3 text-3xl font-semibold text-dark">
              Von Upload bis nachvollziehbarem Ergebnis
            </h2>
            <p class="mt-4 text-sm text-slate-600">
              Platzhaltertext, der den Validierungsablauf über Abteilungen und Partnernetzwerke
              hinweg beschreibt.
            </p>
          </div>
          <div class="space-y-6">
            <div class="rounded-3xl border border-slate-200 bg-slate-50 p-6">
              <p class="text-sm font-semibold text-slate-800">
                1. Upload und Versionierung
              </p>
              <p class="mt-2 text-sm text-slate-600">
                IFC- und Dokument-Sets hochladen. Das System erzeugt automatisch unveränderliche
                Versionen und eine Master-Linie.
              </p>
            </div>
            <div class="rounded-3xl border border-slate-200 bg-slate-50 p-6">
              <p class="text-sm font-semibold text-slate-800">
                2. Validierung ausführen
              </p>
              <p class="mt-2 text-sm text-slate-600">
                Prüfungen per API-Trigger starten. Platzhaltertext für den Python-Validator und
                die Service-Token-Integration.
              </p>
            </div>
            <div class="rounded-3xl border border-slate-200 bg-slate-50 p-6">
              <p class="text-sm font-semibold text-slate-800">
                3. Ergebnisse teilen
              </p>
              <p class="mt-2 text-sm text-slate-600">
                Bericht veröffentlichen, Stakeholder informieren und jede Entscheidung
                nachvollziehbar halten.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="mx-auto max-w-6xl px-6 py-20">
      <div class="flex flex-wrap items-center justify-between gap-6">
        <div>
          <p class="text-xs uppercase tracking-widest text-slate-400">
            Partner
          </p>
          <h2 class="mt-3 text-3xl font-semibold text-dark">
            Zusammenarbeit über Europa hinaus
          </h2>
        </div>
        <p class="max-w-sm text-sm text-slate-500">
          Platzhaltertext für Partnerschaften aus Wien, ganz Österreich und europäischen
          Forschungskonsortien.
        </p>
      </div>

      <div class="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div class="flex h-20 items-center justify-center rounded-2xl border border-slate-200 bg-slate-100 text-xs font-semibold tracking-widest text-slate-500">
          LOGO
        </div>
        <div class="flex h-20 items-center justify-center rounded-2xl border border-slate-200 bg-slate-100 text-xs font-semibold tracking-widest text-slate-500">
          LOGO
        </div>
        <div class="flex h-20 items-center justify-center rounded-2xl border border-slate-200 bg-slate-100 text-xs font-semibold tracking-widest text-slate-500">
          LOGO
        </div>
        <div class="flex h-20 items-center justify-center rounded-2xl border border-slate-200 bg-slate-100 text-xs font-semibold tracking-widest text-slate-500">
          LOGO
        </div>
        <div class="flex h-20 items-center justify-center rounded-2xl border border-slate-200 bg-slate-100 text-xs font-semibold tracking-widest text-slate-500">
          LOGO
        </div>
        <div class="flex h-20 items-center justify-center rounded-2xl border border-slate-200 bg-slate-100 text-xs font-semibold tracking-widest text-slate-500">
          LOGO
        </div>
        <div class="flex h-20 items-center justify-center rounded-2xl border border-slate-200 bg-slate-100 text-xs font-semibold tracking-widest text-slate-500">
          LOGO
        </div>
        <div class="flex h-20 items-center justify-center rounded-2xl border border-slate-200 bg-slate-100 text-xs font-semibold tracking-widest text-slate-500">
          LOGO
        </div>
      </div>
    </section>
  </main>
</template>
