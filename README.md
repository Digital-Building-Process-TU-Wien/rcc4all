# RCC4All

RCC4All is an open-source platform for checking IFC-based BIM models against regulatory and technical requirements.

It is built for both project stakeholders and developers: stakeholders get a clear process for defining and reviewing checks, and developers get a modular system that can be extended and integrated. The prototype is maintained by the Center of Digital Building Processes at TU Wien and is being developed as part of the research project "Regulatory Criteria Check für öffentliche Auftraggeber" (RCC4ÖAG), funded by the FFG COLLECTIVE RESEARCH grant.

## Partners

### Project Partners

- TU Wien – Digitaler Bauprozess
- ASFINAG
- BIG
- ÖBB Infrastruktur
- Land Niederösterreich
- Land Steiermark
- Stadt Wien
- Wiener Linien

### Supporting Partners

- ODE

The project is open for more supporting partners. If you are interested, contact [harald.urban@tuwien.ac.at](mailto:harald.urban@tuwien.ac.at).

## Project Context

Many approval-relevant requirements in construction are still written as natural-language text. BIM models, on the other hand, are digital and machine-readable. This mismatch makes repeatable, transparent validation difficult and often leads to manual or proprietary workflows.

RCC4All closes that gap. It supports a structured path from requirement definition to executable checks and documented results, with a strong focus on open standards and long-term maintainability.

## Donation
Our principle: sharing and distributing research is crucial to learning from each other and moving forward together. If you would like to support our open source research, we greatly appreciate donations.

Technische Universität Wien/Spendenkonto IBAN:  
AT19 3200 0200 0061 1228  
BIC/SWFT:  
RLNWATWW

Purpose of transfer:  
GEV011020ZFT S235030-000 - Digital Building Process

## How It Works

1. Each checking authority (for example, a state building authority or a rail/infrastructure authority) works in its own team space with separate projects, permissions, and model versions.
2. Domain experts and technical users design reusable workflows in the authoring environment.
3. These workflows are exported as an execution plan (JSON) and passed to the runner, which executes the plan against IFC and related input files.
4. Results are returned as structured reports (JSON, BCF, HTML) and, as a planned extension, generated helper geometry in IFC format (planned) to support interpretation and traceability.

## Core Components

### Web Frontend

Location: [./app/web](./app/web)

The web frontend provides the main user interface and is built with [Nuxt 4](https://nuxt.com/). Its central capability is a visual scripting editor where checking nodes are composed into reusable templates and exported as an execution plan JSON for the runner. Optional governance and collaboration views for groups, projects, and files via the [Payload SDK](https://github.com/payloadcms/payload/tree/main/packages/sdk) are also present, though the CMS integration is not currently used.

### Checking Rule Runner

Location: [./app/runner](./app/runner)

The runner is a Python-based CLI engine for executing checking rules. It executes a library of decorator-registered Python functions whose input and output contracts are defined with Pydantic models. It receives an execution plan as a JSON file that defines input files, nodes, their connections, settings, and input bindings, and executes that plan against IFC and IDS input files (additional formats such as Excel/CSV and version-pinned runner hashes in the execution plan are planned). In addition to textual/structured outputs (JSON, BCF, HTML), helper geometry meshes are used internally during geometric checks, with IFC helper-geometry export planned.

In this prototype the web app spawns the python runner directly; this can be replaced by a job queue or separate API in a production setup.

### CMS (not currently used)

Location: [./app/cms](./app/cms)

The CMS is a [Payload](https://payloadcms.com/) prototype for collaboration and governance (groups, projects, user permissions, and versioned project data). It is currently not used in active development; the web frontend runs standalone against local files in `app/web/.dev-files/`. See [CMS README.md](./app/cms/README.md) for details.

## Summary of project goals

RCC4ÖAG is a research project concerned with the formalisation of regulatory and technical requirements for BIM-based model checking. Its objective is to develop a reproducible method for translating textual requirements from standards, guidelines, and public regulations into machine-readable and executable checking logic. The project addresses a practical gap: although BIM models are increasingly exchanged in the open IFC standard, the relevant checking criteria remain largely text-based, which limits automation and often leads to manual or proprietary checking workflows.

To address this, the project develops an open-source prototype platform together with a structured process that links regulatory source text, semantic interpretation, formal rule description, and executable query. The tool is intended to support software-independent checking of IFC-based models and to go beyond simple attribute validation by representing more complex logical, semantic, and geometric conditions. It also investigates a visual rule-definition approach so that domain experts without programming expertise can participate in the creation and adaptation of checking rules, while developers can build on an open, modular, and extensible architecture.

A further focus is the treatment of information generated during checking. Some relevant elements, such as escape routes or daylight-related areas, are not explicitly modelled but must be derived from existing model information. RCC4ÖAG therefore examines how such derived elements and checking results can be stored in open, durable formats rather than being confined to proprietary software environments. Large language models are used only as methodically controlled support for tasks such as information extraction, requirement structuring, and pseudocode generation. Overall, the project aims to establish a transparent and maintainable foundation for regulatory BIM checking, particularly for public-sector use and future standardisation.

## Getting Started for Developers

To set up a local development environment and start contributing:

1. **Install prerequisites**: Node.js 24+ (npm 11.7+), Python 3.11+, and [uv](https://github.com/astral-sh/uv)
2. **See [GettingStarted.md](./GettingStarted.md)** for local node authoring and running workflows, and **[CONTRIBUTING.md](./CONTRIBUTING.md)** for PR guidelines and verification commands

## Development Documentation

Each application has its own README and development guidelines:

- **[app/web/README.md](./app/web/README.md)** – Web frontend (Nuxt 4) setup, architecture, and workflow editor
- **[app/runner/README.md](./app/runner/README.md)** – Checking rule runner (Python) setup and usage
- **[app/cms/README.md](./app/cms/README.md)** – CMS backend (Payload, not currently used)

Code style and patterns are documented in `AGENTS.md` (where present) and each module's README.

## License

This project is developed as part of the RCC4ÖAG research project at TU Wien and is licensed under the [MIT License](./LICENSE).
