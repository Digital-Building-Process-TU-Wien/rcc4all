# CONTRIBUTING

Thank you for you interest in rcc4all, we appreciate your input in our
- [Discussions](https://github.com/Digital-Building-Process-TU-Wien/rcc4all/discussions): General talk around our project, suggestions, clarifications,
usecases - your first stop to get ahold of the maintainers.
- [Issues](https://github.com/Digital-Building-Process-TU-Wien/rcc4all/issues): You found a bug, a typo or want to suggest a well defined new feature?
Please make sure there are no existing issues covering your problem and wait for a confirmation from a team member prior to opening a PR.

## Pull Request Guidelines

- Please follow [conventional branch](https://conventionalbranch.org/) naming (e.g., `feat/element-position-node`, `fix/issue-123`, `chore/update-getting-started`) and [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) messages.
- Check out our [Getting Started Guide](GettingStarted.md) and have a look at the READMEs ([web](/app/web/README.md), [cms](/app/cms/README.md), [runner](/app/runner/README.md)) of the subprojects.
- Run tests and linters — see [Development Tools & Verification](#development-tools--verification) below. The same checks run in CI on every PR.
- Try to stick to existing types (pydantic & ts) and derive from them instead of defining new ones.

## Development Tools & Verification

Each app is checked independently. The commands below are the single source of truth; the GitHub Actions workflow ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the same checks on every PR. CI currently covers the **runner** and **web** apps; the **CMS** is excluded for now (see its section below).

### Runner (`app/runner`) — Python

Requires [uv](https://github.com/astral-sh/uv) (Python 3.11). Install dependencies once, then run all checks:

```bash
cd app/runner
uv sync
```

| Check | Command |
| --- | --- |
| Lint | `uv run ruff check` |
| Format (verify) | `uv run ruff format --check` |
| Format (fix) | `uv run ruff format` |
| Type check | `uv run pyright` |
| Tests | `uv run pytest` |

All-in-one:

```bash
uv run ruff check && uv run ruff format --check && uv run pyright && uv run pytest
```

### Web (`app/web`) — Nuxt

```bash
cd app/web
npm ci
npm run check   # eslint + nuxt typecheck
```

When the runner's node types change, regenerate the committed schema pair and run the checks:

```bash
npm run generate:schema
```

`scripts/schema.json` and `scripts/schema.d.ts` are generated files (see the header in `schema.d.ts`) and are committed; CI fails if they drift from the runner's registry.

### CMS (`app/cms`) — Payload

Not covered by CI yet. Run its checks locally when working on it (see `app/cms/README.md`):

```bash
cd app/cms
npm ci
npm run lint
npm run test
```