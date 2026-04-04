# Open BIM Engine – Web Frontend

## Overview

This is the web frontend for Open BIM Engine, built with [Nuxt 4](https://nuxt.com/) and styled with [Tailwind CSS](https://tailwindcss.com/).

The frontend provides the main user interface for the Open BIM Engine platform, enabling collaboration across contracting authorities. Its central capability is a **visual scripting editor** where checking nodes are composed into reusable templates. From this authoring step, an execution plan JSON is produced and sent to the checking rule runner.

The web frontend communicates with the [Payload CMS](./app/cms) backend via the [Payload SDK](https://github.com/payloadcms/payload/tree/main/packages/sdk) to:
- Manage groups, projects, files, and check runs
- Handle user permissions and authentication (JWT/magic links)
- Trigger validation workflows
- Display results and helper geometry

## Getting Started

### Prerequisites
- **Node.js**: tested with Node 24
- A running CMS backend (see [../cms/README.md](../cms/README.md))

```env
# CMS backend URL (needed for Payload SDK)
PAYLOAD_PUBLIC_API_URL=http://localhost:3000  # or your CMS URL
```

## Key Features & Architecture

### Visual Scripting Editor
The core feature is a no-code editor where domain experts can compose reusable checking templates by connecting nodes. The editor outputs a JSON execution plan for the [runner](../runner).

### Permission Model
- **Super Admins**: Full system access via Payload admin UI
- **Group Admins**: Manage their group(s), invite users, create subgroups
- **Users**: View and create projects within their groups
- **Anonymous**: Access publicly shared projects

Authentication is invite-only via JWT tokens (magic links).

### Integration with CMS

The frontend uses the Payload SDK (configured in [composables/usePayloadSDK.ts](./app/composables/usePayloadSDK.ts)) to:
- Query projects, check runs, and files
- Authenticate users
- Submit workflows for validation

## Development Workflow

### Working with the CMS

The web frontend depends on the CMS backend. To develop locally:

1. **Start the CMS** (in `../cms`):
   ```bash
   cd ../cms
   npm install
   npm run dev
   ```

2. **Start the web frontend** (in this directory):
   ```bash
   npm install
   npm run dev
   ```

3. **Update types** after CMS schema changes:
   ```bash
   # From cms/ directory:
   npm run generate:types
   ```

## See Also

- [Top-level README](../../README.md) – Overview of the entire Open BIM Engine project
- [CMS README](../cms/README.md) – Backend, data model, and API documentation
- [Runner README](../runner/README.md) – Execution engine for checking rules
- [Nuxt Docs](https://nuxt.com/)
- [Tailwind CSS Docs](https://tailwindcss.com/)
