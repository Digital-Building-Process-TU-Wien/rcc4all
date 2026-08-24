# Session Handoff — RCC4ALL

Read this file first at the start of every session. Update it as work
progresses, and record anything that went wrong (e.g. a failing test).

## Current work — `bcf_output` node (LOI-Check → BCF 3.0)
Branch: `feat/BCF-Node`
Plan: see `Plan.md`.
Node memory file: `app/runner/src/openbim_runner/nodes/bcf_output/bcf_output.md`.

### Done
- [x] Read project docs + existing nodes; wrote `Plan.md`; decisions locked.
- [x] Created this handoff file.
- [x] `output_dir` added to `ExecutionContext` (`base.py`) + wired in `workflow.py`.
- [x] Implemented `bcf_output.py` (models + `@node()` + BCF 3.0 writer) + tests + READMEs.
- [x] `bcf_output.md` memory file created; `loi_check.md` naming note updated.
- [x] Registered in `nodes/__init__.py`, `nodes.ts`, `WorkflowNode.vue` terminal handle.
- [x] `npm run generate:schema` (schema.json + schema.d.ts regenerated).
- [x] Verification: runner 145 tests passed, ruff clean, pyright 0 errors; web lint + typecheck clean.

### Next tasks / open items
- None blocking. The node is ready for review/commit.
- Fixed values chosen: `TopicType=ERROR`, `TopicStatus=Open`, `CreationAuthor=RCC4All`; markup includes NO `<Header>` and no viewpoint files (user choice). Revisit if a viewer needs these.

### Naming note
The older draft in `loi_check.md` called the BCF node `bcf_export`; the final
name decided with the user is **`bcf_output`**.

### Constraints / reminders
- **REMINDER (for commit time):** `WorkflowNode.vue` was modified to hide the
  output handle for terminal `bcf_output` nodes (shared component, outside the
  node folder). Call this out before committing/pushing.
- Never touch `main`; no git operations (I do all git work manually).

### Gotchas / issues
- (nothing yet)
