import antfu from '@antfu/eslint-config'
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  antfu({
    typescript: {
      parserOptions: {
        project: false,
      },
    },
    markdown: false,
  }),
  {
    ignores: [
      '.agents/',
      '.vscode/',
      '.nuxt/',
      'node_modules/',
      'dist/',
      '.git/',
      'coverage/',
      '*.md',
      '**/*.md',
    ],
    rules: {
      'no-console': 'warn',
    },
  },
  {
    // The web app has no test runner yet. The path helpers are covered with
    // Node's built-in runner (`npm run test:unit`), not vitest.
    files: ['tests/**/*.ts'],
    rules: {
      'test/no-import-node-test': 'off',
    },
  },
)
