# openBIM Engine - Python Nodes

**Core IFC checking logic for the openBIM engine.**

## Overview

This repository contains the Python-based node workflows and IFC checking logic for the openBIM engine. It provides a CLI interface designed to execute node-based workflows and return detailed checking results for building models.

## Features

- **IFC Processing**: Direct parsing and checking of IFC models.
- **Node Workflows**:  Workflow & node-based execution logic.
- **CLI Tooling**: Command-line calls for executing workflows with inputs and outputs.

## Tech Stack

- **[uv](https://github.com/astral-sh/uv)**: Python package installer and resolver.
- **[Ruff](https://docs.astral.sh/ruff/)**: Python linter and formatter.
- **[IfcOpenShell](http://ifcopenshell.org/)**: Open-source IFC toolkit and geometry engine.

## Getting Started

### Prerequisites

Ensure you have `uv` installed on your system for dependency management.

### Installation

1. Navigate to the project directory:
   ```bash
   cd python-nodes
   ```

2. Install the project dependencies:
   ```bash
   uv sync
   ```

### Linting and Code Formatting

```bash
uv run ruff check
ruff check --fix
```

## VS Code Setup

To use the python virtual environment in VS Code:

1. Open the Command Palette with `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (macOS).
2. Run `Python: Select Interpreter`.
3. Choose the interpreter from the `python-nodes` workspace.
4. Select the Python executable from `./.venv/...`.

Install recommended extensions, should be a popup.