# RCC4All Agent Guide

Monorepo with three applications plus shared packages. Each application documents its own rules and validation steps in its module `AGENTS.md` (or README):

- `app/web` – Nuxt 4 frontend → [AGENTS.md](./app/web/AGENTS.md)
- `app/runner` – Python checking-rule engine → [README.md](./app/runner/README.md)
- `app/cms` – Payload CMS backend → [AGENTS.md](./app/cms/AGENTS.md)
- `shared/` – shared types and packages

## Scratch workspace

Use the gitignored `.scratch/` directory for throwaway work, PLAN.md, tasks that are in-progress, experiments, scratch notes, and intermediate artifacts. Nothing you put there should ever be committed — it stays out of version control. The directory is kept in the repo only via `.gitkeep`, so don't delete it.