# openBIM Engine - Python Nodes

**Core IFC checking logic for the openBIM engine.**

## Minimal Node Layout

The runner uses a minimal function-based node structure under `src/openbim_runner/`:

```text
src/
   openbim_runner/
      main.py
      workflow.py
      nodes/
         base.py
         an_example_node/
            tests/
              test_an_example_node.py
            an_example_node.py
tests/ <-- integration tests / multiple nodes / workflows
   testdata/
      demo.json
      test.ifc
```

- `base.py` defines the shared Pydantic base model, the `@node()` decorator, and the dispatcher.
- Each node is a plain function with one typed settings model, an optional typed inputs model, and one typed result model.
- `element_filter` resolves express IDs for all entities matching an IFC type such as `IFCWALL`.
- `get_name` resolves IFC object names from configured express IDs.
- `concat_string` joins a string list that the workflow resolves before the node is called.

## Implementation Philosophy

The runtime layer stays intentionally small:

- The function signature is the source of truth.
- Pydantic validates inputs and outputs and generates JSON schema.
- The decorator only registers the function and records its models.
- Human-facing documentation such as titles, descriptions, and translations can live outside Python code.

This keeps the execution layer stable while making node metadata easier to manage separately.

The workflow engine now resolves `node_id.field_name` references centrally. Nodes no longer look up upstream outputs themselves.

## Overview

This repository contains the Python-based node workflows and IFC checking logic for the openBIM engine. It provides a CLI interface designed to execute node-based workflows and return detailed checking results for building models.

## Features

- **IFC Processing**: Direct parsing and checking of IFC models.
- **Node Workflows**: Workflow execution built around registered Python functions.
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

### Example Node

```python
from pydantic import Field

from openbim_runner.nodes import ExecutionContext, node
from openbim_runner.nodes.base import NodeModel


class EvaluateSettings(NodeModel):
   allow_missing: bool = Field(default=True)


class EvaluateInputs(NodeModel):
   express_ids: list[int] = Field(default=[])


class EvaluateResult(NodeModel):
   object_names: list[str | None] = Field(default=[])


@node()
async def evaluate(
   settings: EvaluateSettings,
   inputs: EvaluateInputs,
   context: ExecutionContext,
) -> EvaluateResult:
   object_names = []

   for express_id in inputs.express_ids:
      entity = context.ifc_model.by_id(express_id)
      object_name = None if entity is None else getattr(entity, "Name", None)
      if object_name is None and not settings.allow_missing:
         raise ValueError(f"Could not resolve a name for express ID {express_id}.")

      object_names.append(object_name)

   return EvaluateResult(object_names=object_names)
```

The decorator derives the external contract directly from the type hints:

- `settings` must be a Pydantic model.
- `inputs` may be provided as a second Pydantic model.
- The return type must be a Pydantic model.
- The runner may inject an optional `ExecutionContext` as the final parameter for access to runtime services such as the IFC model.

### Dispatcher Example

```python
from openbim_runner.nodes import dispatch

result = await dispatch(
   "evaluate",
   {"allow_missing": True},
   inputs_payload={"express_ids": [12, 34, 56]},
   context=context,
)

print(result.object_names)
```

### Demo Workflow

The minimal runnable prototype lives in `tests/testdata/demo.json` and currently wires:

- `get_name -> concat_string`

The demo fixture expects `test.ifc` in the same directory. Run it with:

```bash
uv run openbim-runner tests/testdata/demo.json
```

To export the JSON schema for all registered nodes:

```bash
uv run openbim-runner export-schema
uv run openbim-runner export-schema node-schema.json
```

The runner currently performs only minimal validation:

- it checks that edge endpoints exist
- it uses both edges and `input_bindings` references to derive execution order
- it resolves `input_bindings` references like `get_name.object_names` before executing each node
- it executes the registered functions and prints their outputs as JSON

Each node now uses a `settings` object plus an optional `input_bindings` object. `settings` is validated against the node's settings model, and the resolved binding payload is validated against the node's inputs model.

## VS Code Setup

To use the python virtual environment in VS Code:

1. Open the Command Palette with `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (macOS).
2. Run `Python: Select Interpreter`.
3. Choose the interpreter from the `python-nodes` workspace.
4. Select the Python executable from `./.venv/...`.

Install recommended extensions, should be a popup.