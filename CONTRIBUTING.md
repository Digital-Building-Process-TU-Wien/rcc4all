# CONTRIBUTING

Thank you for you interest in rcc4all, we appreciate your input in our
- [Discussions](https://github.com/Digital-Building-Process-TU-Wien/rcc4all/discussions): General talk around our project, suggestions, clarifications,
usecases - your first stop to get ahold of the maintainers.
- [Issues](https://github.com/Digital-Building-Process-TU-Wien/rcc4all/issues): You found a bug, a typo or want to suggest a well defined new feature?
Please make sure there are no existing issues covering your problem and wait for a confirmation from a team member prior to opening a PR.

## Pull Request Guidelines

- Please follow [conventional branch](https://conventionalbranch.org/) naming (e.g., `feat/element-position-node`, `fix/issue-123`, `chore/update-getting-started`) and [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) messages.
- Check out our [Getting Started Guide](GettingStarted.md) and have a look at the READMEs ([web](/app/web/README.md), [cms](/app/cms/README.md), [runner](/app/runner/README.md)) of the subprojects.
- Run tests and linters.
- Try to stick to existing types (pydantic & ts) and derive from them instead of defining new ones.