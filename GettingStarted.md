# Getting Started: How to Write a Node and Run the Workflow

A simple guide for beginners to create custom nodes in RCC4All.

## Quick Overview

Node development in RCC4All touches **two parts**:

1. **Web App (Vue/Nuxt)** - Visual node editor where you design workflows
2. **Runner (Python)** - Executes the workflow and processes IFC files

To create a new node, you implement it in **both** places.

> **Prerequisites**: Node.js 24+ (`npm >= 11.7`), Python 3.11+, and [uv](https://github.com/astral-sh/uv). Run `uv sync` in `app/runner` and `npm ci` in `app/web` before starting.

---

## Step 0: Setup IFC Files (Required for Testing)

Before creating nodes, you need IFC files to work with:

### 1. Create the `.dev-files` folder

```bash
cd app/web
mkdir -p .dev-files
```

### 2. Add your IFC files

Copy your IFC files into `app/web/.dev-files/`

Example files:
- `test.ifc`
- `building.ifc`
- `sample.ifc`

### 3. Why `.dev-files`?

- This folder is used for local development files
- The editor's model manager assigns IFC files from this folder
- A `File Input` node selects one of those assigned models
- Workflow JSON and results are also saved here
- The folder is gitignored (not committed to version control)

> **Note**: The `.dev-files` folder is automatically created when you run a workflow, but you should create it beforehand to add IFC files.

---

## Step 1: Plan Your Node

Before coding, define:

- **What does your node do?** (e.g., "prints hello world", "calculates area")
- **What inputs does it need?** (data from upstream nodes)
- **What settings does it have?** (user configuration)
- **What output does it produce?** (data for downstream nodes)

### Example: `template_node`

| Aspect | Value |
|--------|-------|
| **Purpose** | Print a greeting message |
| **Inputs** | `name` (string to greet) |
| **Settings** | `greeting` (custom greeting like "Hello" or "Hi") |
| **Output** | `message` (the final greeting string) |

---

## Step 2: Implement the Python Runner Node

### 2.1 Create Node Directory

```bash
cd app/runner/src/openbim_runner/nodes
mkdir template_node
cd template_node
mkdir tests
```

### 2.2 Create the Node Implementation

**File**: `app/runner/src/openbim_runner/nodes/template_node/template_node.py`

```python
from pydantic import Field
from openbim_runner.nodes.base import NodeModel, node

# 1. Define Settings Model (user configuration)
class TemplateNodeSettings(NodeModel):
    greeting: str = Field(
        default="Hello",
        title="Greeting",
        description="The greeting word to use",
    )

# 2. Define Inputs Model (data from upstream nodes)
class TemplateNodeInputs(NodeModel):
    name: str = Field(
        default="World",
        title="Name",
        description="The name to greet",
    )

# 3. Define Result Model (output data)
class TemplateNodeResult(NodeModel):
    message: str = Field(
        default="",
        title="Message",
        description="The final greeting message",
    )

# 4. Implement the Node Function
@node()  # Decorator registers the node automatically
async def template_node(
    settings: TemplateNodeSettings,
    inputs: TemplateNodeInputs,
) -> TemplateNodeResult:
    """Create a greeting message."""

    # Note: Do not write to stdout with print() — stdout is reserved for the
    # runner's JSON result payload. Write debug logs to sys.stderr if needed.
    message = f"{settings.greeting}, {inputs.name}!"

    return TemplateNodeResult(message=message)
```

### 2.3 Create Documentation (Required!)

Both `README.en.md` and `README.de.md` are required by `export-schema`. In German text, always use **"Node"/"Nodes"** (never "Knoten").

**File**: `app/runner/src/openbim_runner/nodes/template_node/README.en.md`

```markdown
---
title: Template Node
description: A simple node that builds a greeting message.
categories: Demo
---

The `template_node` is a simple example node that demonstrates the basic structure of a node.

## Use case example

Use this node as a starting point for learning how to create new nodes, or as a test node to verify your workflow is working.

## Settings

- **Greeting**: The greeting word to use (e.g., "Hello", "Hi", "Welcome")

## Inputs

- **Name**: The name to greet

## Outputs

- **Message**: The final greeting message (e.g., "Hello, World!")
```

**File**: `app/runner/src/openbim_runner/nodes/template_node/README.de.md`

```markdown
---
title: Template Node
description: Ein einfacher Node, der eine Begrüßungsnachricht erstellt.
categories: Demo
---

Der `template_node` ist ein einfacher Beispiel-Node, der die Grundstruktur eines Nodes demonstriert.

## Anwendungsbeispiel

Verwenden Sie diesen Node als Ausgangspunkt zum Erlernen der Erstellung neuer Nodes oder als Test-Node, um zu überprüfen, ob Ihr Workflow funktioniert.

## Einstellungen

- **Greeting**: Das zu verwendende Grußwort (z.B. "Hello", "Hi", "Welcome")

## Eingaben

- **Name**: Der zu grüßende Name

## Ausgaben

- **Message**: Die endgültige Begrüßungsnachricht (z.B. "Hello, World!")
```

### 2.4 Register the Node

**File**: `app/runner/src/openbim_runner/nodes/__init__.py`

Import and export your node alongside the existing registered nodes:

```python
# ... existing imports ...
from .template_node.template_node import template_node  # ← ADD THIS

__all__ = [
    # ... existing exports ...
    "template_node",  # ← ADD THIS
]
```

### 2.5 Write Tests (Recommended)

**File**: `app/runner/src/openbim_runner/nodes/template_node/tests/test_template_node.py`

```python
import asyncio
from openbim_runner.nodes.template_node.template_node import (
    TemplateNodeSettings,
    TemplateNodeInputs,
    TemplateNodeResult,
    template_node,
)

def test_template_node_basic() -> None:
    # Run the node with default values
    result = asyncio.run(
        template_node(
            TemplateNodeSettings(greeting="Hello"),
            TemplateNodeInputs(name="World"),
        )
    )
    
    # Verify output
    assert result == TemplateNodeResult(message="Hello, World!")

def test_template_node_custom() -> None:
    # Run the node with custom greeting
    result = asyncio.run(
        template_node(
            TemplateNodeSettings(greeting="Hi"),
            TemplateNodeInputs(name="Alice"),
        )
    )
    
    # Verify output
    assert result == TemplateNodeResult(message="Hi, Alice!")
```

---

## Step 3: Implement the Web App Vue Component

### 3.1 Create Vue Component

**File**: `app/web/app/nodes/TemplateNode/TemplateNode.vue`

```vue
<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'

// 1. Define typed node using schema
type TemplateNodeType = SchemaNodeType<'template_node'>

interface Props {
  node: TemplateNodeType
}

const props = defineProps<Props>()
const { t } = useI18n()

// 2. Get scoped reactive reference to the node (auto-imported composable)
const node = useScopedNode<TemplateNodeType>(props.node.id)

// 3. Initialize defaults if needed
if (!node.value.data.settings) {
  node.value.data.settings = { greeting: 'Hello' }
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      {{ t('node.TemplateNode.title') }}
    </div>
  </div>

  <div class="flex flex-col gap-2">
    <!-- Greeting Setting -->
    <label class="text-xs text-slate-500 font-semibold uppercase tracking-tight">
      {{ t('node.TemplateNode.greeting') }}
    </label>
    <input
      v-model="node.data.settings!.greeting"
      type="text"
      :placeholder="t('node.TemplateNode.greetingPlaceholder')"
      class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
    >
  </div>
</template>
```

Add the matching `node.TemplateNode.*` keys to both `app/web/i18n/locales/en.json` and `app/web/i18n/locales/de.json` (see `app/web/AGENTS.md`).

### 3.2 Register the Component (if non-standard name)

**File**: `app/web/app/utils/nodes.ts`

Standard `snake_case` → `PascalCase` names (such as `template_node` → `TemplateNode`) resolve automatically. If your component folder/file name differs from the default PascalCase conversion, add an explicit entry to `nodeNameToComponent`:

```typescript
const nodeNameToComponent: Record<string, string> = {
  // ... existing mappings ...
  template_node: 'TemplateNode', // optional when PascalCase matches
}
```

### 3.3 Generate Schema and Types (One Command!)

From the **web app directory**, run:

```bash
cd app/web
npm run generate:schema
```

This single command:
1. Exports the schema from Python runner → `scripts/schema.json`
2. Generates TypeScript node types → `scripts/schema.d.ts`
3. Generates workflow types and Zod schema → `scripts/workflow-schema.d.ts`, `scripts/workflow-schema.zod.ts`

✅ Your node is now fully registered in both Python and TypeScript!

---

## Step 4: Test Your Node

### 4.1 Verify `.dev-files` Setup

Make sure you have:

1. Created the `app/web/.dev-files/` folder
2. Added at least one IFC file (e.g., `test.ifc`)

```bash
cd app/web
ls .dev-files/  # Should show your IFC files
```

### 4.2 Start the Web App

```bash
cd app/web
npm run dev
```

### 4.3 Create a Workflow

1. **Open the node editor**: `http://localhost:3001/node-demo`

2. **Assign the main IFC file**:
   - Use **Add IFC Model** in the editor model bar
   - Select `test.ifc`; it is stored in the workflow with the reserved slug `main`

3. **Add an Ifc Element Filter**:
   - Drag `Ifc Element Filter` to the canvas
   - Add a `File Input` node and select the `main` model
   - Connect File Input's `model_slug` output to the filter's `model_slug` input
   - The filter now scans the assigned main model

4. **Add your Template Node**:
   - Drag `Template Node` to the canvas
   - Set `greeting` to "Hi"
   - The unbound `name` input uses its default value, `World`

5. **Run the workflow**:
   - Click "Run Workflow"
   - Check the node output in the results view
   - You should see `message`: `"Hi, World!"`

### 4.4 What Happens When You Run

1. **Workflow JSON is saved** to `.dev-files/workflow-{timestamp}.json`
2. **Python runner executes** the workflow
3. **Results are saved** to `.dev-files/results-{timestamp}.json`
4. **Results are displayed** in the browser

---

## Quick Reference

### Python Node Patterns

| Pattern | Settings | Inputs | Context | Example |
|---------|----------|--------|---------|---------|
| Settings only | ✓ | ✗ | ✗ | `file_input`, `set_3d_position_rotation` |
| Settings + Inputs | ✓ | ✓ | ✗ | `template_node`, `concat_string`, `comparison` |
| Settings + Inputs + Context | ✓ | ✓ | ✓ | `ifc_element_filter`, `generate_3d_cube`, `loi_check` |

### Function Signature Rules

```python
@node()
async def my_node(
    settings: MySettings,      # Optional
    inputs: MyInputs,          # Optional
    context: ExecutionContext, # Optional (must be last)
) -> MyResult:                 # Required
    ...
```

**Rules**:

- Must have at least one parameter (`settings`, `inputs`, or `context`)
- `context` must be the last parameter
- Maximum 3 parameters
- Settings, inputs, and return types should inherit from `NodeModel` (which enforces Pydantic `extra="forbid"`)

### Vue Component Template

```vue
<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'

type MyNode = SchemaNodeType<'my_node'>

interface Props {
  node: MyNode
}

const props = defineProps<Props>()
const { t } = useI18n()
const node = useScopedNode<MyNode>(props.node.id)

// Initialize defaults
if (!node.value.data.settings) {
  node.value.data.settings = { defaultValue: 'value' }
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold">
      {{ t('node.MyNode.title') }}
    </div>
  </div>

  <div class="flex flex-col gap-2">
    <!-- Bind to node.data.settings -->
    <input v-model="node.data.settings!.myValue">
  </div>
</template>
```

---

## Common Pitfalls

1. ❌ **Forgetting to register the node** in `nodes/__init__.py`
2. ❌ **Missing `README.en.md` / `README.de.md`** - The schema generator expects locale-suffixed READMEs (plain `README.md` is ignored)
3. ❌ **Calling `print()` inside a node** - Writes to stdout and corrupts the runner's JSON output; use `sys.stderr` for debug logs
4. ❌ **Type mismatch** - Ensure Python and Vue types match
5. ❌ **Wrong function signature** - Follow the parameter order rules
6. ❌ **Missing `@node()` decorator** - Node won't be registered
7. ❌ **No IFC file in `.dev-files`** - Workflow will fail if no file is available

---

## File Structure Summary

```
app/web/
├── .dev-files/               # Local development files (gitignored)
│   ├── test.ifc             # Your IFC test files ← ADD HERE
│   ├── workflow-*.json      # Generated workflow files
│   └── results-*.json       # Generated results (when run from web app)
├── app/nodes/MyNode/
│   └── MyNode.vue           # Vue component
├── app/utils/nodes.ts       # Optional custom component mapping
├── i18n/locales/
│   ├── en.json              # English UI translations
│   └── de.json              # German UI translations
└── scripts/
    ├── schema.json          # Generated node & workflow schema
    ├── schema.d.ts          # Generated node TS types
    ├── workflow-schema.d.ts # Generated workflow TS types
    └── workflow-schema.zod.ts

app/runner/src/openbim_runner/nodes/my_node/
├── my_node.py               # Implementation
├── README.en.md             # English docs (required)
├── README.de.md             # German docs (required)
└── tests/
    └── test_my_node.py      # Tests (recommended)

app/runner/src/openbim_runner/nodes/__init__.py  # Python registration
```

---

## Commands Reference

```bash
# Generate schema + types (from web directory)
cd app/web
npm run generate:schema

# Run a workflow (from runner directory)
cd app/runner
uv run openbim-runner run path/to/workflow.json

# Run tests (from runner directory)
cd app/runner
uv run pytest

# Start web dev server
cd app/web
npm run dev

# List .dev-files
cd app/web
ls .dev-files/
```

---

## Complete Example Workflow

Here's what a complete workflow JSON looks like:

```json
{
  "files": [
    {
      "path": "test.ifc",
      "slug": "main",
      "hash": ""
    }
  ],
  "nodes": [
    {
      "id": "file_input",
      "type": "file_input",
      "label": "Select main model",
      "settings": {
        "slug": "main"
      }
    },
    {
      "id": "walls",
      "type": "ifc_element_filter",
      "label": "Find walls",
      "settings": {
        "filter_rows": [
          {
            "mode": "include",
            "entity_type": "IFCWALL",
            "predefined_type": "",
            "property_set": "",
            "property_name": "",
            "operator": "==",
            "value": ""
          }
        ]
      },
      "input_bindings": {
        "model_slug": "file_input.model_slug"
      }
    },
    {
      "id": "greet_node",
      "type": "template_node",
      "label": "Say Hello",
      "settings": {
        "greeting": "Hi"
      }
    }
  ],
  "edges": [
    {
      "source": "file_input",
      "target": "walls"
    }
  ]
}
```

This workflow:

1. Assigns `test.ifc` to the reserved `main` model slot
2. Routes the `main` model slug into an IFC element filter
3. Runs the template node with greeting "Hi" and the default name "World"
4. Outputs: `"Hi, World!"`
5. Saves results to `.dev-files/results-{timestamp}.json` when executed from the web app (CLI runs print JSON to stdout)

---
