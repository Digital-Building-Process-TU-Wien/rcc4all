// Ambient stub for Payload's runtime module so the `declare module 'payload'` 
// augmentation in `app/cms/src/payload-types.ts` resolves when those types are
// re-exported into the Nuxt frontend, where the `payload` package is not installed.
// The frontend only consumes the generated entity interfaces and never imports
// from `payload` at runtime.
declare module 'payload' {}
