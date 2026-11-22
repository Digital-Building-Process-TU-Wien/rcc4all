from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from rcc4all_runner.schemas import DEFAULT_SCHEMAS_DIR, export_schemas
from rcc4all_runner.workflow import (
    dump_results,
    execute_workflow,
    load_workflow,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rcc4all-runner",
        description="Run RCC4All workflow checks from the command line.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Run a workflow JSON file.",
    )
    run_parser.add_argument(
        "workflow",
        help="Path to the workflow JSON file.",
    )

    export_parser = subparsers.add_parser(
        "export-schema",
        help="Export per-node and workflow JSON Schemas into a target directory.",
    )
    export_parser.add_argument(
        "output",
        nargs="?",
        help=f"Output directory path (defaults to {DEFAULT_SCHEMAS_DIR}).",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a workflow JSON file without running it.",
    )
    validate_parser.add_argument(
        "workflow",
        help="Path to the workflow JSON file.",
    )

    inspect_parser = subparsers.add_parser(
        "inspect-models",
        help="Tessellate local test IFC models and export OBJ inspection artifacts.",
    )
    inspect_parser.add_argument(
        "--category",
        default=None,
        help="Only process this category (e.g. rail, large_models).",
    )
    inspect_parser.add_argument(
        "--pattern",
        default=None,
        help="Only process models whose filename stem matches (case-insensitive).",
    )
    inspect_parser.add_argument(
        "--express-id",
        type=int,
        default=None,
        help="Also export this single express ID as OBJ for each processed model.",
    )
    inspect_parser.add_argument(
        "--models-root",
        type=Path,
        default=None,
        help="Root directory containing categorized IFC test models.",
    )
    inspect_parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=None,
        help="Root directory for generated OBJ artifacts.",
    )
    return parser


def normalize_argv(argv: Sequence[str] | None) -> list[str]:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {
        "run",
        "validate",
        "export-schema",
        "inspect-models",
        "-h",
        "--help",
    }:
        return arguments

    return ["run", *arguments]


def export_registry_schema(output: str | None) -> int:
    target_dir = DEFAULT_SCHEMAS_DIR if output is None else Path(output).resolve()
    written = export_schemas(target_dir)
    print(f"Wrote {len(written)} schema files to {target_dir}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_argv(argv))

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "export-schema":
        return export_registry_schema(args.output)

    if args.command == "validate":
        validate_path = Path(args.workflow).resolve()
        try:
            load_workflow(validate_path)
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            print(error)
            return 1
        print(f"OK: {validate_path}")
        return 0

    if args.command == "inspect-models":
        from rcc4all_runner.inspect_models import MODELS_ROOT, inspect_models

        models_root = args.models_root or MODELS_ROOT
        artifacts_root = args.artifacts_root or (
            Path(MODELS_ROOT).parent.parent / "artifacts"
        )
        return inspect_models(
            models_root,
            artifacts_root,
            category=args.category,
            pattern=args.pattern,
            express_id=args.express_id,
        )

    workflow_path = Path(args.workflow).resolve()

    try:
        node_outputs, node_lookup = execute_workflow(workflow_path)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(error)
        return 1

    print(dump_results(node_outputs, node_lookup))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
