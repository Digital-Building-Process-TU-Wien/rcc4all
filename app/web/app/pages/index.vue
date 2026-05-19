<script setup lang="ts">
import type { CardBlock, Page, PageSectionBlock } from 'rcc4all-payload-types'

const sdk = usePayloadSDK()
const { currentLocale } = usei18n()

const { data: homePage } = await useAsyncData(
  'home-page',
  async () => {
    const result = await sdk.find({
      collection: 'pages',
      where: {
        slug: {
          equals: 'home',
        },
      },
      limit: 1,
      locale: currentLocale.value,
      fallbackLocale: false,
    })

    return (result.docs[0] ?? null) as Page | null
  },
  {
    watch: [currentLocale],
  },
)

const heroLinks = computed(() => {
  const links = []

  if (homePage.value?.hero.primaryLink?.label && homePage.value.hero.primaryLink.to) {
    links.push({
      label: homePage.value.hero.primaryLink.label,
      to: homePage.value.hero.primaryLink.to,
      icon: 'i-lucide-arrow-right',
    })
  }

  if (homePage.value?.hero.secondaryLink?.label && homePage.value.hero.secondaryLink.to) {
    links.push({
      label: homePage.value.hero.secondaryLink.label,
      to: homePage.value.hero.secondaryLink.to,
      color: 'neutral' as const,
      variant: 'subtle' as const,
      icon: 'i-lucide-arrow-right',
    })
  }

  return links
})

const pageSections = computed(() => {
  return (homePage.value?.layout ?? []).filter(isPageSectionBlock)
})

function isPageSectionBlock(value: Page['layout'] extends infer Layout ? Layout extends (infer Item)[] | null ? Item : never : never): value is PageSectionBlock {
  return value?.blockType === 'page-section'
}

function isCardBlock(value: PageSectionBlock['cards'] extends infer Cards ? Cards extends (infer Item)[] | null ? Item : never : never): value is CardBlock {
  return value?.blockType === 'card'
}

function getSectionCards(section: PageSectionBlock): CardBlock[] {
  return (section.cards ?? []).filter(isCardBlock)
}

function resolveCardIcon(card: CardBlock): string {
  return card.icon || 'i-lucide-layout-panel-top'
}
</script>

<template>
  <UPage>
    <UPageHero
      v-if="homePage"
      :headline="homePage.hero.headline ?? homePage.title"
      :title="homePage.hero.title"
      :description="homePage.hero.description"
      orientation="vertical"
      :links="heroLinks"
    >
      <UCard class="bg-elevated">
        <div class="space-y-4">
          <div
            v-for="fact in homePage.hero.facts ?? []"
            :key="fact.id ?? fact.label"
            class="rounded-lg border border-default bg-default px-4 py-3"
          >
            <p class="text-xs font-semibold uppercase tracking-widest text-muted">
              {{ fact.label }}
            </p>
            <p class="mt-2 text-sm text-toned">
              {{ fact.value }}
            </p>
          </div>
        </div>
      </UCard>
    </UPageHero>

    <UPageSection
      v-for="section in pageSections"
      :id="section.anchor || undefined"
      :key="section.id ?? section.anchor ?? section.title"
      :headline="section.headline || undefined"
      :title="section.title"
      :description="section.description || undefined"
    >
      <UPageGrid v-if="section.display === 'grid'" class="lg:grid-cols-2">
        <UCard
          v-for="card in getSectionCards(section)"
          :key="card.id ?? card.title"
          class="h-full"
        >
          <div class="flex h-full flex-col gap-4">
            <div class="flex items-start gap-3">
              <UIcon :name="resolveCardIcon(card)" class="mt-1 size-5 text-primary" />
              <div class="space-y-3">
                <UBadge v-if="card.badge" color="neutral" variant="soft">
                  {{ card.badge }}
                </UBadge>
                <div>
                  <h3 class="text-base font-semibold text-highlighted">
                    {{ card.title }}
                  </h3>
                  <p class="mt-2 text-sm text-toned">
                    {{ card.description }}
                  </p>
                </div>
              </div>
            </div>

            <div v-if="card.link?.label && card.link.to" class="mt-auto">
              <UButton
                :to="card.link.to"
                color="neutral"
                variant="subtle"
                trailing-icon="i-lucide-arrow-right"
              >
                {{ card.link.label }}
              </UButton>
            </div>
          </div>
        </UCard>
      </UPageGrid>

      <div v-else class="space-y-4">
        <UCard
          v-for="card in getSectionCards(section)"
          :key="card.id ?? card.title"
        >
          <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div class="flex items-start gap-3">
              <UIcon :name="resolveCardIcon(card)" class="mt-1 size-5 text-primary" />
              <div class="space-y-3">
                <UBadge v-if="card.badge" color="neutral" variant="soft">
                  {{ card.badge }}
                </UBadge>
                <div>
                  <h3 class="text-base font-semibold text-highlighted">
                    {{ card.title }}
                  </h3>
                  <p class="mt-2 text-sm text-toned">
                    {{ card.description }}
                  </p>
                </div>
              </div>
            </div>

            <UButton
              v-if="card.link?.label && card.link.to"
              :to="card.link.to"
              color="neutral"
              variant="subtle"
              trailing-icon="i-lucide-arrow-right"
            >
              {{ card.link.label }}
            </UButton>
          </div>
        </UCard>
      </div>
    </UPageSection>
  </UPage>
</template>
