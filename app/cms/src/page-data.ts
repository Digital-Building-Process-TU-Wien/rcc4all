import type { Page, PageSectionBlock } from './payload-types'

export type SupportedLocale = 'en' | 'de'

export interface PageSeedData {
  title: string
  hero: Page['hero']
  layout: PageSectionBlock[]
}

export const homePageContent: Record<SupportedLocale, PageSeedData> = {
  en: {
    title: 'Home',
    hero: {
      headline: 'RCC4All / RCC4OEAG',
      title: 'Open-source research platform for IFC-based checking.',
      description:
        'RCC4All is a research prototype for transparent checking of IFC-based BIM models against regulatory and technical requirements.',
      badges: [{ label: 'Research Prototype' }, { label: 'IFC-based' }, { label: 'Open Source' }],
      facts: [
        {
          label: 'Institution',
          value: 'TU Wien, Center of Digital Building Processes',
        },
        {
          label: 'Context',
          value: 'RCC4OEAG research project, funded by FFG COLLECTIVE RESEARCH',
        },
        {
          label: 'License',
          value: 'Open source under the MIT License',
        },
      ],
      primaryLink: {
        label: 'Projects',
        to: '/projects',
      },
      secondaryLink: {
        label: 'Login',
        to: '/login',
      },
    },
    layout: [
      {
        blockType: 'page-section',
        blockName: 'Research context',
        anchor: 'research-context',
        headline: 'Research Context',
        title: 'From regulatory text to executable checks.',
        description:
          'The project explores how textual requirements can be translated into machine-readable and executable checking logic.',
        display: 'grid',
        cards: [
          {
            blockType: 'card',
            title: 'Problem',
            description:
              'Requirements are usually written as natural-language text, while BIM models are machine-readable.',
            icon: 'i-lucide-file-search',
          },
          {
            blockType: 'card',
            title: 'Goal',
            description:
              'RCC4All turns that gap into transparent, reproducible, openly documented checks.',
            icon: 'i-lucide-target',
          },
          {
            blockType: 'card',
            title: 'Approach',
            description:
              'The project connects domain rule definition, visual authoring, and executable workflows based on open standards.',
            icon: 'i-lucide-waypoints',
          },
        ],
      },
      {
        blockType: 'page-section',
        blockName: 'Platform',
        headline: 'Platform',
        title: 'Three components, one workflow.',
        description:
          'RCC4All combines governance, authoring, and execution in an open architecture.',
        display: 'grid',
        cards: [
          {
            blockType: 'card',
            title: 'CMS',
            description: 'Manages groups, projects, permissions, and versioned project data.',
            icon: 'i-lucide-database',
          },
          {
            blockType: 'card',
            title: 'Web Frontend',
            description: 'Provides the collaboration UI and the visual workflow editor.',
            icon: 'i-lucide-panels-top-left',
          },
          {
            blockType: 'card',
            title: 'Runner',
            description: 'Executes JSON-based plans against IFC and other input files.',
            icon: 'i-lucide-play-square',
          },
        ],
      },
      {
        blockType: 'page-section',
        blockName: 'Process',
        headline: 'Process',
        title: 'How the prototype is used.',
        description:
          'The documented flow runs from groups and projects to reports and helper geometry.',
        display: 'rows',
        cards: [
          {
            blockType: 'card',
            title: '1. Organize',
            description:
              'Each checking authority works in its own groups, projects, and versioned data spaces.',
            icon: 'i-lucide-folder-tree',
          },
          {
            blockType: 'card',
            title: '2. Author',
            description:
              'Domain and technical users create reusable workflows in the visual editor.',
            icon: 'i-lucide-pencil-ruler',
          },
          {
            blockType: 'card',
            title: '3. Execute',
            description:
              'The runner processes the execution plan and returns reports plus helper geometry.',
            icon: 'i-lucide-play-square',
          },
        ],
      },
      {
        blockType: 'page-section',
        blockName: 'Subpages',
        headline: 'Subpages',
        title: 'Relevant entry points in the current prototype.',
        description:
          'These routes already exist in the web app and provide access to the current prototype surfaces.',
        display: 'grid',
        cards: [
          {
            blockType: 'card',
            title: 'Projects',
            description: 'Browse project spaces, files, and workflow results.',
            icon: 'i-lucide-folder-kanban',
            link: {
              label: 'Open projects',
              to: '/projects',
            },
          },
          {
            blockType: 'card',
            title: 'Groups',
            description: 'Inspect the collaboration and permission structure.',
            icon: 'i-lucide-users',
            link: {
              label: 'Open groups',
              to: '/groups',
            },
          },
          {
            blockType: 'card',
            title: 'Login',
            description: 'Access the authenticated workspace for invited users.',
            icon: 'i-lucide-key-round',
            link: {
              label: 'Open login',
              to: '/login',
            },
          },
          {
            blockType: 'card',
            title: 'Node Demo',
            description: 'Experimental workflow canvas illustrating the editor concept.',
            icon: 'i-lucide-workflow',
            badge: 'Experimental',
            link: {
              label: 'Open demo',
              to: '/node-demo',
            },
          },
        ],
      },
      {
        blockType: 'page-section',
        blockName: 'Status',
        headline: 'Status',
        title: 'Research prototype with an open, extensible foundation.',
        description:
          'RCC4All is developed as an open research prototype aimed at a maintainable foundation for regulatory BIM checking.',
        display: 'rows',
        cards: [
          {
            blockType: 'card',
            title: 'Current scope',
            description:
              'The current platform connects research, governance, and prototype workflow execution.',
            icon: 'i-lucide-info',
          },
        ],
      },
    ],
  },
  de: {
    title: 'Startseite',
    hero: {
      headline: 'RCC4All / RCC4OEAG',
      title: 'Open-Source-Forschungsplattform für IFC-basiertes Prüfen.',
      description:
        'RCC4All ist ein Forschungsprototyp zur nachvollziehbaren Prüfung von IFC-basierten BIM-Modellen gegen regulatorische und technische Anforderungen.',
      badges: [{ label: 'Forschungsprototyp' }, { label: 'IFC-basiert' }, { label: 'Open Source' }],
      facts: [
        {
          label: 'Institution',
          value: 'TU Wien, Center of Digital Building Processes',
        },
        {
          label: 'Kontext',
          value: 'RCC4OEAG-Forschungsprojekt, gefördert durch FFG COLLECTIVE RESEARCH',
        },
        {
          label: 'Lizenz',
          value: 'Open Source unter der MIT-Lizenz',
        },
      ],
      primaryLink: {
        label: 'Projekte',
        to: '/projects',
      },
      secondaryLink: {
        label: 'Login',
        to: '/login',
      },
    },
    layout: [
      {
        blockType: 'page-section',
        blockName: 'Forschungskontext',
        anchor: 'research-context',
        headline: 'Forschungskontext',
        title: 'Von regulatorischem Text zu ausführbaren Prüfungen.',
        description:
          'Das Projekt untersucht, wie textuelle Anforderungen in maschinenlesbare und prüfbare Logik überführt werden können.',
        display: 'grid',
        cards: [
          {
            blockType: 'card',
            title: 'Ausgangslage',
            description:
              'Anforderungen liegen meist als natürlichsprachiger Text vor, BIM-Modelle dagegen maschinenlesbar.',
            icon: 'i-lucide-file-search',
          },
          {
            blockType: 'card',
            title: 'Ziel',
            description:
              'RCC4All soll daraus nachvollziehbare, reproduzierbare und offen dokumentierte Prüfungen machen.',
            icon: 'i-lucide-target',
          },
          {
            blockType: 'card',
            title: 'Ansatz',
            description:
              'Das Projekt verbindet fachliche Regeldefinition, visuelle Modellierung und ausführbare Workflows auf Basis offener Standards.',
            icon: 'i-lucide-waypoints',
          },
        ],
      },
      {
        blockType: 'page-section',
        blockName: 'Plattform',
        headline: 'Plattform',
        title: 'Drei Bausteine, ein Workflow.',
        description:
          'RCC4All kombiniert Governance, Authoring und Ausführung in einer offenen Architektur.',
        display: 'grid',
        cards: [
          {
            blockType: 'card',
            title: 'CMS',
            description:
              'Verwaltet Gruppen, Projekte, Berechtigungen und versionierte Projektdaten.',
            icon: 'i-lucide-database',
          },
          {
            blockType: 'card',
            title: 'Web Frontend',
            description:
              'Bietet die Benutzeroberfläche für Zusammenarbeit und den visuellen Workflow-Editor.',
            icon: 'i-lucide-panels-top-left',
          },
          {
            blockType: 'card',
            title: 'Runner',
            description:
              'Führt JSON-basierte Ausführungspläne gegen IFC- und andere Eingabedateien aus.',
            icon: 'i-lucide-play-square',
          },
        ],
      },
      {
        blockType: 'page-section',
        blockName: 'Ablauf',
        headline: 'Ablauf',
        title: 'Wie der Prototyp eingesetzt wird.',
        description:
          'Die dokumentierte Prozesskette reicht von Gruppen und Projekten bis zu Berichten und Helper Geometry.',
        display: 'rows',
        cards: [
          {
            blockType: 'card',
            title: '1. Organisieren',
            description:
              'Jede prüfende Organisation arbeitet in eigenen Gruppen, Projekten und Versionsständen.',
            icon: 'i-lucide-folder-tree',
          },
          {
            blockType: 'card',
            title: '2. Modellieren',
            description:
              'Fachliche und technische Beteiligte erstellen wiederverwendbare Workflows im visuellen Editor.',
            icon: 'i-lucide-pencil-ruler',
          },
          {
            blockType: 'card',
            title: '3. Ausführen',
            description:
              'Der Runner verarbeitet den Ausführungsplan und liefert Berichte sowie Helper Geometry.',
            icon: 'i-lucide-play-square',
          },
        ],
      },
      {
        blockType: 'page-section',
        blockName: 'Unterseiten',
        headline: 'Unterseiten',
        title: 'Relevante Einstiege in den aktuellen Prototyp.',
        description:
          'Diese Routen sind bereits Teil der Webanwendung und führen in die bestehende Struktur.',
        display: 'grid',
        cards: [
          {
            blockType: 'card',
            title: 'Projekte',
            description: 'Projektbereiche, Dateien und Ausführungsergebnisse aufrufen.',
            icon: 'i-lucide-folder-kanban',
            link: {
              label: 'Projekte öffnen',
              to: '/projects',
            },
          },
          {
            blockType: 'card',
            title: 'Gruppen',
            description: 'Kollaborations- und Berechtigungsstruktur ansehen.',
            icon: 'i-lucide-users',
            link: {
              label: 'Gruppen öffnen',
              to: '/groups',
            },
          },
          {
            blockType: 'card',
            title: 'Login',
            description: 'Zugang zum geschützten Bereich für eingeladene Nutzerinnen und Nutzer.',
            icon: 'i-lucide-key-round',
            link: {
              label: 'Login öffnen',
              to: '/login',
            },
          },
          {
            blockType: 'card',
            title: 'Knoten-Demo',
            description:
              'Experimentelle Workflow-Ansicht zur Veranschaulichung des Editor-Konzepts.',
            icon: 'i-lucide-workflow',
            link: {
              label: 'Demo öffnen',
              to: '/node-demo',
            },
          },
        ],
      },
      {
        blockType: 'page-section',
        blockName: 'Projektstand',
        headline: 'Projektstand',
        title: 'Forschungsprototyp mit offener und erweiterbarer Grundlage.',
        description:
          'RCC4All wird als offener Forschungsprototyp entwickelt und soll eine langfristig wartbare Grundlage für regulatorisches BIM-Checking schaffen.',
        display: 'rows',
        cards: [
          {
            blockType: 'card',
            title: 'Aktueller Stand',
            description:
              'Die aktuelle Plattform verbindet Forschung, Governance und prototypische Workflow-Ausführung.',
            icon: 'i-lucide-info',
          },
        ],
      },
    ],
  },
}

export function getHomePageData(locale: SupportedLocale): PageSeedData {
  return homePageContent[locale]
}
