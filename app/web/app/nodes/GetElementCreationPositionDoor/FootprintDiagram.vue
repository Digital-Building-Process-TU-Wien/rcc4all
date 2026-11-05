<script setup lang="ts">
interface Props {
  selectedPointIndex?: number
}

interface Point {
  x: number
  y: number
}

const props = defineProps<Props>()

const { t } = useI18n()

const p1 = { x: 70, y: 130 }
const p2 = { x: 170, y: 130 }
const p3 = { x: 170, y: 200 }
const p4 = { x: 70, y: 200 }
const p5 = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 }
const p6 = { x: (p3.x + p4.x) / 2, y: (p3.y + p4.y) / 2 }
const p7 = { x: 120, y: 165 }

const points: Record<number, Point> = {
  1: p1,
  2: p2,
  3: p3,
  4: p4,
  5: p5,
  6: p6,
  7: p7,
}

function getPoint(index: number): Point {
  return points[index] ?? p7
}

const doorWidth = p2.x - p1.x
const hinge = p1

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
    <svg viewBox="0 0 240 220" class="w-full h-auto">
      <!-- Wand -->
      <rect
        x="10"
        y="130"
        width="220"
        height="70"
        class="fill-slate-100 stroke-slate-300 stroke-2"
        rx="2"
      />

      <!-- Türöffnung -->
      <rect
        x="70"
        y="130"
        :width="doorWidth"
        height="70"
        class="fill-white stroke-slate-400 stroke-1 stroke-dasharray-2"
        rx="2"
      />

      <!-- Türblatt (geöffnet) -->
      <line
        :x1="hinge.x"
        :y1="hinge.y"
        :x2="hinge.x"
        :y2="hinge.y - doorWidth"
        class="stroke-slate-400 stroke-2 stroke-dasharray-2"
      />

      <!-- Schwenkbogen -->
      <path
        :d="`M ${p2.x} ${p2.y} A ${doorWidth} ${doorWidth} 0 0 0 ${hinge.x} ${hinge.y - doorWidth}`"
        class="fill-none stroke-slate-400 stroke-2 stroke-dasharray-2"
      />

      <!-- Richtungs-Labels -->
      <text x="120" y="10" text-anchor="middle" class="fill-slate-500 text-[9px] uppercase">
        {{ t('node.getElementCreationPositionDoor.diagram.front') }}
      </text>
      <text x="120" y="213" text-anchor="middle" class="fill-slate-500 text-[9px] uppercase">
        {{ t('node.getElementCreationPositionDoor.diagram.back') }}
      </text>

      <!-- Punkte P1-P7 -->
      <circle
        v-for="index in [1, 2, 3, 4, 5, 6, 7]"
        :key="index"
        :cx="getPoint(index).x"
        :cy="getPoint(index).y"
        :r="index === 7 ? 10 : 6"
        :class="getPointClass(index)"
      />

      <!-- Punkt-Labels -->
      <text
        v-for="index in [1, 2, 3, 4, 5, 6, 7]"
        :key="index"
        :x="getPoint(index).x"
        :y="getPoint(index).y - (index === 7 ? 15 : 10)"
        text-anchor="middle"
        class="text-[10px] font-semibold"
        :class="getLabelClass(index)"
      >
        P{{ index }}
      </text>

    </svg>
  </div>
</template>
