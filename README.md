# RCC4All

RCC4All is an open-source platform for checking IFC-based BIM models against regulatory and technical requirements.

It is built for both project stakeholders and developers: stakeholders get a clear process for defining and reviewing checks, and developers get a modular system that can be extended and integrated. The prototype is maintained by the Center of Digital Building Processes at TU Wien and is being developed as part of the research project "Regulatory Criteria Check für öffentliche Auftraggeber" (RCC4ÖAG), funded by the FFG COLLECTIVE RESEARCH grant.

## Project Context

Many approval-relevant requirements in construction are still written as natural-language text. BIM models, on the other hand, are digital and machine-readable. This mismatch makes repeatable, transparent validation difficult and often leads to manual or proprietary workflows.

RCC4All closes that gap. It supports a structured path from requirement definition to executable checks and documented results, with a strong focus on open standards and long-term maintainability.

## How It Works

1. Each checking authority (for example, a state building authority or a rail/infrastructure authority) works in its own team space with separate projects, permissions, and model versions.
2. Domain experts and technical users design reusable workflows in the authoring environment.
3. These workflows are exported as an execution plan (JSON) and passed to the runner, which executes the plan against IFC and related input files.
4. Results are returned as reports and generated helper geometry, which support interpretation and traceability.

## Core Components

### Web Frontend

Location: [./app/web](./app/web)

The web frontend provides the main user interface and is built with [Nuxt 4](https://nuxt.com/). In the current research project, it offers practical governance and collaboration views for working with groups, projects, and files through the [Payload SDK](https://github.com/payloadcms/payload/tree/main/packages/sdk), making the multi-authority workflow manageable. Its central capability is a visual scripting editor where checking nodes are composed into reusable templates. From this authoring step, an execution plan JSON is produced for the runner. The architecture also keeps the editor concept portable beyond the current workspace logic, so it can be reused in setups where governance and storage are provided differently.

### Checking Rule Runner

Location: [./app/runner](./app/runner)

The runner is a Python-based CLI engine for execution checking rules. It executes a library of decorator-registered Python functions whose input and output contracts are defined with Pydantic models. It receives an execution plan as a JSON file that defines nodes, their connections, inputs, outputs, and result names, and it includes the implementation version of the runner as an integral part of the plan (git hash, release tag, python wheel hash). The runner then executes that version-pinned plan against input files (for example IFC, IDS, Excel, and CSV). In addition to textual outputs, it can produce helper geometry in IFC format to document how checks were performed, such as temporary collision meshes, measured distances, and other derived geometric artifacts.

In this prototype the web app spawns the python runner directly, this can be replaced by a job queue or seperate API in a production setup.

### CMS

Location: [./app/cms](./app/cms)

The CMS is the collaboration and governance layer of the platform. It manages groups, projects, user permissions, and versioned project data, including IFC files, workflow plans, and partial checking results. It enables multiple teams to work in parallel while keeping clear access boundaries and an auditable project structure. The CMS is built with [Payload](https://payloadcms.com/). See [CMS README.md](./app/cms/README.md) for implementation details.

Within this project phase, the CMS is our prototype approach to make collaboration workable across project partners. Its purpose is to let different checking authorities run their own checking tasks independently, without forcing everyone to navigate or manage each other's project spaces.

## Summary of project goals

RCC4ÖAG is a research project concerned with the formalisation of regulatory and technical requirements for BIM-based model checking. Its objective is to develop a reproducible method for translating textual requirements from standards, guidelines, and public regulations into machine-readable and executable checking logic. The project addresses a practical gap: although BIM models are increasingly exchanged in the open IFC standard, the relevant checking criteria remain largely text-based, which limits automation and often leads to manual or proprietary checking workflows.

To address this, the project develops an open-source prototype platform together with a structured process that links regulatory source text, semantic interpretation, formal rule description, and executable query. The tool is intended to support software-independent checking of IFC-based models and to go beyond simple attribute validation by representing more complex logical, semantic, and geometric conditions. It also investigates a visual rule-definition approach so that domain experts without programming expertise can participate in the creation and adaptation of checking rules, while developers can build on an open, modular, and extensible architecture.

A further focus is the treatment of information generated during checking. Some relevant elements, such as escape routes or daylight-related areas, are not explicitly modelled but must be derived from existing model information. RCC4ÖAG therefore examines how such derived elements and checking results can be stored in open, durable formats rather than being confined to proprietary software environments. Large language models are used only as methodically controlled support for tasks such as information extraction, requirement structuring, and pseudocode generation. Overall, the project aims to establish a transparent and maintainable foundation for regulatory BIM checking, particularly for public-sector use and future standardisation.

## Getting Started for Developers

To set up a local development environment and start contributing:

1. **Install prerequisites**: Node.js 24+, Python 3+
2. **See [CONTRIBUTING.md](./CONTRIBUTING.md)** for detailed setup instructions and development workflows

## Development Documentation

Each application has its own README and development guidelines:

- **[app/web/README.md](./app/web/README.md)** – Web frontend (Nuxt 4) setup, architecture, and component library
- **[app/cms/README.md](./app/cms/README.md)** – CMS backend (Payload) setup, data model, and API
- **[app/runner/README.md](./app/runner/README.md)** – Validation engine (Python) setup and usage  

Code style and patterns are documented in `AGENTS.md` files within each module.

## License

This project is developed as part of the RCC4ÖAG research project at TU Wien and is licensed under the [MIT License](./LICENSE).