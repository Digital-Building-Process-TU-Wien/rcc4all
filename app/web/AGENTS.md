## Linting & Typechecking

Before committing, always run:

```bash
npm run lint
npm run typecheck
```

This ensures your code passes ESLint and TypeScript validation.

## Styling
Use Tailwindcss only have a look at the main.css for some project wide presets.

### Avoid Arbitrary Values

Use existing design tokens (spacing scale, colors, sizes).
Avoid arbitrary values unless absolutely necessary.

**✅ Do**
<div class="mt-lg p-sm">

**❌ Don’t**
<div class="mt-[18px] p-[7px]">

## Functions

- Use **named function declarations** for top-level and exported functions.
- Arrow functions are acceptable for:
  - Inline callbacks (e.g., `.map(x => x.id)`)
  - Short expressions where hoisting isn't needed

✅ Do:
function parseConfig(input) {
  return JSON.parse(input);
}

users.map(u => u.name);

❌ Avoid:
const parseConfig = (input) => {
  return JSON.parse(input);
};

## Vue

- Define a `Props` interface at the top of the file and use `defineProps<Props>()`.
- Use `withDefaults(defineProps<Props>(), { ... })` for defaults.
- Avoid runtime prop objects and the `type:` field in `defineProps`.
- Avoid tailwind classes in script tag, they belong in the template.

## Nuxt Auto-Imports

Nuxt auto-imports Vue APIs and composables. Never manually import `ref`, `reactive`, `computed`, `watch`, or Nuxt composables.

**✅ Do:**
```typescript
const count = ref(0)
const doubled = computed(() => count.value * 2)
```

**❌ Don't:**
```typescript
import { computed, ref } from 'vue'
```

## TypeScript Types

### Node Types

Use `SchemaNodeType<K>` from `~/utils/schema-helpers` for Vue Flow node components. This reuses the generated schema types from `scripts/schema.d.ts` (source of truth from Python).

**✅ Do:**
```typescript
import type { SchemaNodeType } from '~/utils/schema-helpers'

type ConcatNode = SchemaNodeType<'concat_string'>
const node = useScopedNode<ConcatNode>(props.id)
```

**❌ Don't:**
```typescript
interface NodeData extends Node {
  data: {
    settings?: { separator?: string }
    result?: { value?: string }
  }
}
```

## Pinia Store Patterns

### Flow Store

Use `useFlowStore()` to access nodes, edges, and viewport.

**✅ Do:**
```typescript
const store = useFlowStore()
const { nodes, hasNodes } = storeToRefs(store)

store.addNodes({
  id: nanoid(),
  type: 'custom',
  position: { x: 100, y: 100 },
  data: { label: 'My Node' },
})

store.updateNodeData(nodeId, { settings: { value: 42 } })
```

**❌ Don't:**
```typescript
const { addNodes } = useVueFlow()

store.nodesById[id] = newNode
```

### Scoped Node Access

Use `useScopedNode(id)` in node components for two-way binding:

**✅ Do:**
```typescript
const node = useScopedNode<MyNodeData>(props.id)

const value = node.value.data.settings.myValue
node.value.data.settings.myValue = newValue
```

**❌ Don't:**
```typescript
props.node.data!.settings = newValue

const { updateNodeData } = useVueFlow()
updateNodeData(props.id, { ... })
```
