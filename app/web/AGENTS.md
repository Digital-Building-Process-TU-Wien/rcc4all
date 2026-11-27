## Linting, Typechecking & Tests

Before committing, run:

```bash
npm run check      # npm run lint + npm run typecheck
npm run test:unit
```

## Styling
Use Tailwind CSS utility classes. Font theme tokens live in `app/assets/css/main.css`.

### Avoid Arbitrary Values

Use Tailwind's spacing scale, colors, and sizes instead of arbitrary values unless necessary.

**✅ Do**
<div class="mt-4 p-2">

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

Use `SchemaNodeType<K>` from `~/schemas` for Vue Flow node components. This reuses the generated per-node schema types from `app/schemas/generated/` (derived from `shared/schemas/`).

**✅ Do:**
```typescript
import type { SchemaNodeType } from '~/schemas'

type ConcatNode = SchemaNodeType<'concat_string'>
const node = useScopedNode<ConcatNode>(props.node.id)
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
  type: availableNode.nodeName,
  position: { x: 100, y: 100 },
  data: createNodeData(availableNode),
})

store.updateNodeData(nodeId, { settings: { value: 42 } })
```

**❌ Don't:**
```typescript
const { addNodes } = useVueFlow()

store.nodesById[id] = newNode
```

### Scoped Node Access

Use `useScopedNode(id)` in node settings components for two-way binding:

**✅ Do:**
```typescript
type MyNode = SchemaNodeType<'my_node'>
const node = useScopedNode<MyNode>(props.node.id)

const value = node.value.data.settings?.myValue
node.value.data.settings!.myValue = newValue
```

**❌ Don't:**
```typescript
props.node.data!.settings = newValue

const { updateNodeData } = useVueFlow()
updateNodeData(props.id, { ... })
```

## Internationalization (i18n)

The node web UI must be fully bilingual (en/de). Never hardcode user-facing strings.

- Translate all UI text through `t()` from the auto-imported `useI18n()`.
- Add every key to **both** `i18n/locales/en.json` and `de.json` in the same change.
- Group node keys under `node.<NodeName>.<...>` and reuse existing keys when the wording matches.
- Align new wording with existing locale text — including the German convention **"Node"/"Nodes"** (never "Knoten").

**✅ Do:**
```typescript
const { t } = useI18n()
label: t('node.<NodeName>.title')
```

**❌ Don't:**
```typescript
label: 'Title'
```
