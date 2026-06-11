# Getting Started: How to Write a Node and Run the Workflow

A simple guide for beginners to create custom nodes in the Open BIM Engine.

## Quick Overview

The Open BIM Engine has **two parts**:

1. **Web App (Vue/Nuxt)** - Visual node editor where you design workflows
2. **Runner (Python)** - Executes the workflow and processes IFC files

To create a new node, you implement it in **both** places.

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
- The `FileInput` node reads files from this folder
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
    """Print a greeting message."""
    
    # Create the greeting message
    message = f"{settings.greeting}, {inputs.name}!"
    
    # Print to console (visible in runner output)
    print(message)
    
    return TemplateNodeResult(message=message)
```

### 2.3 Create Documentation (Required!)

**File**: `app/runner/src/openbim_runner/nodes/template_node/README.en.md`

```markdown
---
title: Template Node
description: A simple node that prints a greeting message.
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

**File**: `app/runner/src/openbim_runner/nodes/template_node/README.de.md` (Optional German translation)

```markdown
---
title: Template Knoten
description: Ein einfacher Knoten, der eine Begrüßungsnachricht ausgibt.
categories: Demo
---

Der `template_node` ist ein einfacher Beispielknoten, der die Grundstruktur eines Knotens demonstriert.

## Anwendungsbeispiel

Verwenden Sie diesen Knoten als Ausgangspunkt zum Erlernen der Erstellung neuer Knoten oder als Testknoten, um zu überprüfen, ob Ihr Workflow funktioniert.

## Einstellungen

- **Greeting**: Das zu verwendende Grußwort (z.B. "Hello", "Hi", "Welcome")

## Eingaben

- **Name**: Der zu grüßende Name

## Ausgaben

- **Message**: Die endgültige Begrüßungsnachricht (z.B. "Hello, World!")
```

### 2.4 Register the Node

**File**: `app/runner/src/openbim_runner/nodes/__init__.py`

Add your import and export:

```python
from .base import ExecutionContext, NodeDefinition, NodeModel, dispatch, get_registry, get_registry_schema, node
from .concat_string.concat_string import concat_string
from .element_filter.element_filter import element_filter
from .generate_3d_cube.generate_3d_cube import generate_3d_cube
from .get_name.get_name import get_name
from .template_node.template_node import template_node  # ← ADD THIS

__all__ = [
    "ExecutionContext",
    "NodeDefinition",
    "NodeModel",
    "concat_string",
    "dispatch",
    "element_filter",
    "generate_3d_cube",
    "get_name",
    "get_registry",
    "get_registry_schema",
    "node",
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
import { useScopedNode } from '~/composables/useScopedNode'

// 1. Define typed node using schema
type TemplateNodeType = SchemaNodeType<'template_node'>

const props = defineProps<{
  node: TemplateNodeType
}>()

// 2. Get scoped reactive reference to the node
const node = useScopedNode<TemplateNodeType>(props.node.id)

// 3. Initialize defaults if needed
if (!node.value.data.settings) {
  node.value.data.settings = { greeting: 'Hello' }
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      Template Node
    </div>
  </div>

  <div class="flex flex-col gap-2">
    <!-- Greeting Setting -->
    <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Greeting</label>
    <input
      v-model="node.data.settings!.greeting"
      type="text"
      placeholder="Hello"
      class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
    />
  </div>
</template>
```

### 3.2 Register the Component

**File**: `app/web/app/utils/nodes.ts`

Add the mapping in `nodeNameToComponent`:

```typescript
const nodeNameToComponent: Record<string, string> = {
  concat_string: 'ConcatString',
  element_filter: 'ElementFilter',
  file_input: 'FileInput',
  generate_3d_cube: 'Generate3DCube',
  get_name: 'GetName',
  template_node: 'TemplateNode',  // ← ADD THIS
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
2. Generates TypeScript types → `scripts/schema.d.ts`

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

2. **Add a File Input node** (to specify the IFC file):
   - Drag `File Input` to canvas
   - Click on it and select an IFC file from the list

3. **Add your Template Node**:
   - Drag `Template Node` to canvas
   - Set `greeting` to "Hi"

4. **Connect nodes** (optional):
   - You can connect File Input's output to Template Node's input if your node uses IFC data

5. **Run workflow**:
   - Click "Run Workflow" button
   - Watch the console output in the results view
   - You should see: `"Hi, World!"`

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
| Settings + Inputs | ✓ | ✓ | ✗ | `template_node`, `concat_string` |
| Settings + Inputs + Context | ✓ | ✓ | ✓ | `get_name` |
| Settings + Context | ✓ | ✗ | ✓ | `element_filter` |
| Inputs + Context | ✗ | ✓ | ✓ | `generate_3d_cube` |

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

- Must have at least `settings` OR `inputs`
- `context` must be the last parameter
- Maximum 3 parameters
- All models must inherit from `NodeModel`
- Return type must be a `NodeModel` subclass

### Vue Component Template

```vue
<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type MyNode = SchemaNodeType<'my_node'>

const props = defineProps<{ node: MyNode }>()
const node = useScopedNode<MyNode>(props.node.id)

// Initialize defaults
if (!node.value.data.settings) {
  node.value.data.settings = { defaultValue: 'value' }
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold">Node Title</div>
  </div>
  
  <div class="flex flex-col gap-2">
    <!-- Bind to node.data.settings -->
    <input v-model="node.data.settings!.myValue" />
  </div>
</template>
```

---

## Common Pitfalls

1. ❌ **Forgetting to register the node** in `__init__.py`
2. ❌ **Missing README.md** - The schema generator needs documentation
3. ❌ **Type mismatch** - Ensure Python and Vue types match
4. ❌ **Wrong function signature** - Follow the parameter order rules
5. ❌ **Missing `@node()` decorator** - Node won't be registered
6. ❌ **No IFC file in `.dev-files`** - Workflow will fail if no file is available

---

## File Structure Summary

```
app/web/
├── .dev-files/               # Local development files (gitignored)
│   ├── test.ifc             # Your IFC test files ← ADD HERE
│   ├── workflow-*.json      # Generated workflow files
│   └── results-*.json       # Generated results
├── app/nodes/MyNode/
│   └── MyNode.vue           # Vue component
└── app/utils/nodes.ts       # Component registration

app/runner/src/openbim_runner/nodes/my_node/
├── my_node.py               # Implementation
├── README.en.md             # English docs (required)
├── README.de.md             # German docs (optional)
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
  "ifc_path": "test.ifc",
  "nodes": [
    {
      "id": "file_input",
      "type": "file_input",
      "label": "Select IFC File",
      "filename": "test.ifc"
    },
    {
      "id": "greet_node",
      "type": "template_node",
      "label": "Say Hello",
      "settings": {
        "greeting": "Hi"
      },
      "inputs": {
        "name": "Alice"
      }
    }
  ],
  "edges": []
}
```

This workflow:

1. Selects `test.ifc` from `.dev-files/`
2. Runs the template node with greeting "Hi" and name "Alice"
3. Outputs: `"Hi, Alice!"`
4. Prints the message to the console
5. Saves results to `.dev-files/results-{timestamp}.json`

---
