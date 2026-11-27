# RCC4All – Web Frontend

## Overview

This is the web frontend for RCC4All, built with [Nuxt 4](https://nuxt.com/) and styled with [Tailwind CSS](https://tailwindcss.com/).

The frontend provides the main user interface for the RCC4All platform, enabling collaboration across contracting authorities. Its central capability is a **visual scripting editor** where checking nodes are composed into reusable templates. From this authoring step, an execution plan JSON is produced and sent to the checking rule runner.

The web frontend also contains optional [Payload CMS](../cms) integration via the [Payload SDK](https://github.com/payloadcms/payload/tree/main/packages/sdk) (not currently used — leave `NUXT_PUBLIC_PAYLOAD_URL` empty to run standalone). Planned CMS-backed features include:
- Managing groups, projects, files, and check runs (planned)
- Invite-only authentication with magic links (planned; current CMS login is email/password)
- Triggering validation workflows via CMS and displaying helper geometry (planned)

## Getting Started

### Prerequisites
- **Node.js**: 24+ (`npm >= 11.7`)
- **Python 3.11+** and **[uv](https://github.com/astral-sh/uv)** (with `uv sync` run in `../runner`) for workflow execution and schema generation

```env
# Optional: Payload CMS API URL (leave empty to disable CMS calls; not currently used)
NUXT_PUBLIC_PAYLOAD_URL=
# Local CMS example: http://localhost:3000/api
```

## Key Features & Architecture

### Visual Scripting Editor
The core feature is a no-code editor where domain experts can compose reusable checking templates by connecting nodes. The editor outputs a JSON execution plan for the [runner](../runner).

### Workflow Execution

The visual scripting editor produces a workflow JSON that is executed by the [runner](../runner). The flow:
1. User creates nodes and connects them on the canvas
2. IFC models are assigned to named slots via the **Add IFC Model** button in the editor header. The reserved `main` slot is required; other slots have unique slugs. These slots are serialized as the workflow's `files` member. A **File Input** node selects one assigned model and outputs its slug. Connect it to an **IFC Element Filter** node's `model_slug` input to choose the model that the filter scans. Other IFC consumers select their model from each qualified reference, such as `main:expr:123`.
3. Workflow JSON is saved to `.dev-files/` and passed to the Python runner
4. Results are displayed on `/results` and saved to `.dev-files/`

### Current multi-model contract

Multi-model workflows use these contracts:

- Workflows list assigned IFC models in `files`; the main file uses the slug `main`.
- A File Input node selects one of those models with `settings.slug`.
- IFC node inputs use qualified references such as `main:expr:123`.
- Bind `ifc_element_filter.express_ids` before passing references to downstream IFC consumers. A bound empty list remains empty and does not trigger whole-model scanning.

### Saving and loading workflows

**Save** and **Load** sit at the right end of the model bar. Named workflows are stored under `app/web/.dev-files/workflow/` by default; the save dialog can place them in any folder inside `app/web/.dev-files` and lists the files already there, so an existing workflow can be picked and overwritten instead of creating a duplicate.

The saved file is the runner payload (`{ files, nodes, edges }`) plus each node's canvas `position`, so a workflow with a `main` model assigned can be executed directly — the runner rejects a workflow without one. Model paths are written relative to the workflow file (the runner's native convention) and translated back to `.dev-files`-relative paths when the file is loaded in the editor.

### Integration with CMS *(not currently used)*

Optional Payload CMS integration is configured in [composables/usePayloadSDK.ts](./app/composables/usePayloadSDK.ts) (disabled when `NUXT_PUBLIC_PAYLOAD_URL` is unset). Currently wired to read `pages` and `groups` and handle email/password login; full CMS-backed projects, check runs, magic links, and workflow submission are planned.

## Development Workflow

1. **Install and start the web frontend** (in `app/web`):
   ```bash
   npm ci
   npm run dev
   ```
   The dev server runs on `http://localhost:3001` (workflow editor at `/node-demo`).

2. **Generate runner schema types** (after runner changes or initial setup):
   ```bash
   npm run generate:schema
   ```
   Exports the Python per-node and workflow JSON Schemas from `../runner` into `../../shared/schemas/` and regenerates `app/schemas/generated/`.

3. **Run checks and tests**:
   ```bash
   npm run check
   npm run test:unit
   ```

## See Also

- [Top-level README](../../README.md) – Overview of the entire RCC4All project
- [CMS README](../cms/README.md) – Backend, data model, and API documentation *(not currently used)*
- [Runner README](../runner/README.md) – Execution engine for checking rules
- [Nuxt Docs](https://nuxt.com/)
- [Tailwind CSS Docs](https://tailwindcss.com/)
