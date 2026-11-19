"""Reading a workflow document from disk and resolving its file paths."""

from __future__ import annotations

from pathlib import Path

from openbim_runner.workflow.model import WorkflowDefinition
from openbim_runner.workflow.validate import validate_workflow


def load_workflow(workflow_path: Path) -> WorkflowDefinition:
    workflow = WorkflowDefinition.model_validate_json(
        workflow_path.read_text(encoding="utf-8")
    )
    validate_workflow(workflow)
    return workflow


def resolve_ifc_path(workflow_path: Path, ifc_path: str) -> Path:
    candidate_path = Path(ifc_path)
    if candidate_path.is_absolute():
        return candidate_path

    return workflow_path.parent / candidate_path
