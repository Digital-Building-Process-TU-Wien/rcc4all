<script setup lang="ts">
const props = defineProps<{
  selectedPointIndex?: number
}>()

const { t } = useI18n()

// Punkt-Koordinaten im SVG-System (viewBox: 0 0 200 150)
const points = {
  1: { x: 40, y: 40 },
  2: { x: 160, y: 40 },
  3: { x: 160, y: 110 },
  4: { x: 40, y: 110 },
  7: { x: 100, y: 75 },
}

// P5 und P6 korrekt berechnen (Mittelpunkte)
points[5] = {
  x: (points[1].x + points[2].x) / 2,
  y: (points[1].y + points[2].y) / 2,
}
points[6] = {
  x: (points[3].x + points[4].x) / 2,
  y: (points[3].y + points[4].y) / 2,
}

function getPointClass(index: number) {
  if (props.selectedPointIndex === index) {
    return 'fill-blue-500 stroke-blue-700 stroke-2'
  }
  return 'fill-slate-400 stroke-slate-600 stroke-1'
}

function getLabelClass(index: number) {
  if (props.selectedPointIndex === index) {
    return 'fill-blue-700 font-bold'
  }
  return 'fill-slate-600'
}
</script>

<template>
  <div class="mt-2 mb-3 border border-slate-200 rounded bg-slate-50 p-3">
    <div class="text-xs font-semibold text-slate-600 mb-2 text-center">
      {{ t('node.getElementCreationPositionDoor.diagram.label') }}
    </div>
    <svg viewBox="0 0 200 150" class="w-full h-auto">
      <!-- Außenrechteck (Footprint) -->
      <rect
        x="20"
        y="20"
        width="160"
        height="110"
        class="fill-white stroke-slate-300 stroke-2"
        rx="2"
      />

      <!-- Verbindungslinien (diagonal für bessere Visualisierung) -->
      <line x1="40" y1="40" x2="160" y2="110" class="stroke-slate-200 stroke-1" />
      <line x1="160" y1="40" x2="40" y2="110" class="stroke-slate-200 stroke-1" />

      <!-- Mittellinien -->
      <line x1="100" y1="40" x2="100" y2="110" class="stroke-slate-200 stroke-1 stroke-dasharray-2" />
      <line x1="40" y1="75" x2="160" y2="75" class="stroke-slate-200 stroke-1 stroke-dasharray-2" />

      <!-- Punkte P1-P7 -->
      <circle
        v-for="index in [1, 2, 3, 4, 5, 6, 7]"
        :key="index"
        :cx="points[index as keyof typeof points].x"
        :cy="points[index as keyof typeof points].y"
        :r="index === 7 ? 10 : 6"
        :class="getPointClass(index)"
      />

      <!-- Punkt-Labels -->
      <text
        v-for="index in [1, 2, 3, 4, 5, 6, 7]"
        :key="index"
        :x="points[index as keyof typeof points].x"
        :y="points[index as keyof typeof points].y - (index === 7 ? 15 : 10)"
        text-anchor="middle"
        class="text-[10px] font-semibold"
        :class="getLabelClass(index)"
      >
        P{{ index }}
      </text>

      <!-- Richtungs-Labels -->
      <text x="100" y="15" text-anchor="middle" class="fill-slate-500 text-[9px] uppercase">
        {{ t('node.getElementCreationPositionDoor.diagram.front') }}
      </text>
      <text x="100" y="145" text-anchor="middle" class="fill-slate-500 text-[9px] uppercase">
        {{ t('node.getElementCreationPositionDoor.diagram.back') }}
      </text>
    </svg>
  </div>
</template>
