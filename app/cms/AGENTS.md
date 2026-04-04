# Payload CMS Development Rules

You are an expert Payload CMS developer. These rules are now split into focused files under .cursor/rules.

Always consult the Index below for further information on the inner workings of payload.

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


## Core Principles

1. **TypeScript-First**: Always use TypeScript with proper types from Payload
2. **Security-Critical**: Follow all security patterns, especially access control
3. **Type Generation**: Run `generate:types` script after schema changes
4. **Transaction Safety**: Always pass `req` to nested operations in hooks
5. **Access Control**: Understand Local API bypasses access control by default
6. **Access Control**: Ensure roles exist when modifiyng collection or globals with access controls

## Code Validation

- To validate typescript correctness after modifying code run `tsc --noEmit`
- Generate import maps after creating or modifying components.

## Index

### [Configuration](.cursor/rules/configuration.md)

Guidance for project-wide setup, Payload config structure, and environment conventions.

### [Collections](.cursor/rules/collections.md)

Rules for defining collections, fields, access, and admin options.

### [Fields](.cursor/rules/fields.md)

Field type usage, validation patterns, and common field configurations.

### [Critical Security Patterns](.cursor/rules/security-critical.md)

Mandatory security practices for access control, auth, and data safety.

### [Access Control](.cursor/rules/access-control.md)

Access strategies, role checks, and request-based permissions.

### [Hooks](.cursor/rules/hooks.md)

Lifecycle hook guidelines, transaction safety, and `req` propagation.

### [Queries](.cursor/rules/queries.md)

Local API usage, query patterns, and performance considerations.

### [Getting Payload Instance](.cursor/rules/getting-payload-instance.md)

How to safely obtain and use the Payload instance in code.

### [Components](.cursor/rules/components.md)

Custom component conventions, import maps, and admin UI integration.

### [Custom Endpoints](.cursor/rules/endpoints.md)

Endpoint routing patterns, auth handling, and request/response best practices.

### [Drafts & Versions](.cursor/rules/drafts-and-versions.md)

Versioning workflows, draft behavior, and publish strategies.

### [Field Type Guards](.cursor/rules/field-type-guards.md)

Type-guard helpers for safely narrowing Payload field types.

### [Plugins](.cursor/rules/plugin-development.md)

Plugin setup, configuration, and extension patterns.

### [Best Practices](.cursor/rules/best-practices.md)

Recommended patterns for maintainability, performance, and consistency.

### [Common Gotchas](.cursor/rules/common-gotchas.md)

Known pitfalls and how to avoid them in Payload projects.

### [Additional Context Files](.cursor/rules/additional-context-files.md)

Pointers to supplemental docs and cross-cutting references.

### [Resources](.cursor/rules/resources.md)

External references and learning materials for Payload CMS.

# Best Practices

## Security

1. Always set `overrideAccess: false` when passing `user` to Local API
2. Field-level access only returns boolean (no query constraints)
3. Default to restrictive access, gradually add permissions
4. Never trust client-provided data
5. Use `saveToJWT: true` for roles to avoid database lookups

## Performance

1. Index frequently queried fields
2. Use `select` to limit returned fields
3. Set `maxDepth` on relationships to prevent over-fetching
4. Use query constraints over async operations in access control
5. Cache expensive operations in `req.context`

## Data Integrity

1. Always pass `req` to nested operations in hooks
2. Use context flags to prevent infinite hook loops
3. Enable transactions for MongoDB (requires replica set) and Postgres
4. Use `beforeValidate` for data formatting
5. Use `beforeChange` for business logic

## Type Safety

1. Run `generate:types` after schema changes
2. Import types from generated `payload-types.ts`
3. Type your user object: `import type { User } from '@/payload-types'`
4. Use `as const` for field options
5. Use field type guards for runtime type checking

## Organization

1. Keep collections in separate files
2. Extract access control to `access/` directory
3. Extract hooks to `hooks/` directory
4. Use reusable field factories for common patterns
5. Document complex access control with comments