# Payload base - A starter template for group based project managment in Payload CMS

## Overview
An admin backend that serves as a base project with simple default collections that can be reused in a group / project / files / version scenario.

## Quickstart

### Prerequisites
- Node.js (see `package.json` engines)
- npm (see `package.json` engines)
- A `.env` file with `PAYLOAD_SECRET` and `DATABASE_URL` set

### Start
1. Install dependencies: `npm install`
2. Run the dev server: `npm run dev`
3. (Optional) Seed demo data: `npm run seed`

### Other Scripts
- `dev`: Start Payload in development mode
- `build`: Build the Payload app
- `start`: Start the production build
- `payload`: Run the Payload CLI for migrations and other admin tasks
- `generate:types`: Generate Payload TypeScript types
- `generate:importmap`: Generate the Payload admin import map
- `seed`: Seed the dev database with demo data
- `test`: Run Vitest integration tests


## Data Model

**Group** title, parent (nullable), admins[], users[]
- Nestable

**Project** title, description, images[], titleImage, group (relation), creator

**WorkflowRun** name, timestamp, project (relation), inputFiles[], outputFiles[]
- Stores validation/check executions per project

**File** project (relation), path, meta fields, type (free-text classification)
- Immutable
- Example types: IFC model files, validation results, supporting documents, issue reports

## Validation Integration
- Checking Rule Runner (Python) executed on local machine or via job queue
- Triggers: workflow run creation (manual or automated via Payload hooks)
- Runner writes results as WorkflowRun data or File records via API

## Auth
- JWT-based
- Email/password + magic link login
- No self-registration; admins invite users
- Service token for other services (no user account)

## User Roles & Permissions

| Role | Capabilities |
|------|--------------|
| **Super Admin** | Create root groups, appoint group admins, full system access, uses Payload admin UI |
| **Group Admin** | Manage users in their group, create subgroups, appoint subgroup admins, edit/delete all projects in group |
| **User** | View projects in their group(s), create projects, manage own projects |
| **Anonymous** | View projects in the special group "public" |

- Hierarchical group structure (theoretical unlimited nesting, limit at 5 for usability)
- Admins inherit admin rights to all descendant subgroups

## Usecase in RCC4All
- **This Backend**: PayloadCMS, SQLite, local file storage
- **A user facing Frontend**: Nuxt 4 (types shared from Payload)
- **File Validation Runner**: Python (separate service)
