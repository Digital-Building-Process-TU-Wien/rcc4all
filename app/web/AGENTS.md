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
- Keep `script setup` simple and do not mix type-based and runtime prop styles.
- Avoid tailwind classes in script tag, they belong in the template.
