# Node Development Prompt (RCC4ALL)

## Usage notes (delete before sending)
- This is a universal prompt for starting work on a new RCC4ALL node.
- Send the ENTIRE "Prompt" section below verbatim each time.

---

## Prompt

You are contributing to **RCC4ALL**, an open-source BIM checking platform
that uses visual scripting to check IFC models. A "node" is implemented in
**two places that must stay in sync**: a Python function in the runner
(source of truth for logic and types) and a Vue/Nuxt component in the web
app (editor UI). Your task: develop a new node.
Use the question tool if you need additional information.

### Workflow (follow in order)
1. Read THIS file first to understand your role and constraints.
2. Read the project docs to understand architecture and conventions and:
   `GettingStarted.md`, `README.md`, `app/web/README.md`, `app/cms/README.md`, `app/runner/README.md`. Code style and patterns are documented in `AGENTS.md` files within each module.
3. Ask me which node to create. This is NOT a single question — ask
   iteratively and go deeper until you fully understand: node name, category,
   settings, inputs, outputs, data types, behavior, and edge cases.
4. Present a step-by-step implementation plan and get approval before coding. Create Tasks. We will save the plan to `Plan.md`.
5. Create the node in BOTH places (layout & registration below).
6. Fill the node spec, decisions, and any edge cases into `[NODE_NAME].md`.
7. Run the project's verification procedure (commands below) and report results.
8. Ensure `[NODE_NAME].md` is fully up to date before finishing.

### Session Handoff File
ALWAYS read `SessionHandoff.md` first at the start of every session (if existing).
To see what we have already done and what are the next tasks to do, create `SessionHandoff.md` (if not existing).
Keep it uptudate. Also document there what went wrong, e.g. a Test failed.

### Node layout & registration
Runner — `app/runner/src/openbim_runner/nodes/<name>/<name>.py`:
- Pydantic model(s) inherited from `NodeModel` (extra="forbid"): optional
  `Settings`, optional `Inputs`, required `Result`; optional `ExecutionContext`
  as last param (max 3 params).
- `@node()` decorator registers the function.
- `README.en.md` required (frontmatter `title`/`description`/`categories`)
  plus `README.de.md` translation; `tests/test_<name>.py`.
- Register the import + export in `nodes/__init__.py`.

Web — `app/web/app/nodes/<PascalName>/<PascalName>.vue`:
- Use `SchemaNodeType<'name'>`, `useScopedNode`, a `Props` interface, Nuxt
  auto-imports, and Tailwind design tokens (see `app/web/AGENTS.md`).
- Register the mapping in `app/web/app/utils/nodes.ts`.
- Run `npm run generate:schema` (in `app/web`) to export Python schema → TS
  types; Python is the single source of truth for types.

Reuse existing pydantic and TS types instead of defining new ones when
possible. Add IFC test files under `app/web/.dev-files/`.

### Verification
Runner (in `app/runner`): `uv run pytest`, `uv run ruff check`, `uv run pyright`.
Web (in `app/web`): `npm run lint`, `npm run typecheck`.

### Constraints (follow strictly)
- Implement BOTH the runner and web parts; the node isn't done until both
   exist and register.
- Only modify files specific to this node/scoped task. Never change general,
   shared, or unrelated files.
- If you believe a change outside the node scope is unavoidable, STOP and ask
   me for permission first.
- Follow existing conventions (naming, style, data types, registration,
   `AGENTS.md`). Don't invent behavior, data types, or conventions — ask me or
   follow the project docs if uncertain.

### Node memory file (`[NODE_NAME].md`)
- Create this file inside the node's directory when the node is created.
- It starts as a compressed copy of this entire prompt, with blank
   placeholder fields for the node specification.
- Complete it with the node spec and decisions during clarification, and
   keep it updated over time with future changes, edge cases, and notes.
- ALWAYS read `[NODE_NAME].md` first at the start of every session,
   before asking any questions, so I never have to repeat information
   that is already saved (protects against context loss).
- It is covered by the scope rule: only modify files within the node's
   directory.

### Git compliance
- NEVER touch the `main` branch.
- NEVER create commits, push, open pull requests, or perform any other
   git operation. I will do all git work manually.
- You are only allowed to create/edit the node's files locally; all
   branching, committing, and sharing is handled by me.

### Before finishing
- Run the verification commands above and report results.
- Update the node's `README.en.md`/`README.de.md` as needed.
- Update `[NODE_NAME].md` with any final changes/discoveries made during
   implementation.
- Summarize what you changed, list any remaining open questions, and
   confirm the work is ready for me to review/commit.
