from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from openbim_runner.nodes import get_registry_schema
from openbim_runner.workflow import dump_results, execute_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openbim-runner",
        description="Run openBIM workflow checks from the command line.",
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
        help="Export JSON schema for all registered nodes.",
    )
    export_parser.add_argument(
        "output",
        nargs="?",
        help="Optional output file path. Prints to stdout when omitted.",
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
        "export-schema",
        "inspect-models",
        "-h",
        "--help",
    }:
        return arguments

    return ["run", *arguments]


def dump_registry_schema() -> str:
    return json.dumps(get_registry_schema(), indent=2)


def export_registry_schema(output: str | None) -> int:
    schema_payload = dump_registry_schema()
    if output is None:
        print(schema_payload)
        return 0

    output_path = Path(output).resolve()
    output_path.write_text(f"{schema_payload}\n", encoding="utf-8")
    print(f"Wrote node schema to {output_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_argv(argv))

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "export-schema":
        return export_registry_schema(args.output)

    if args.command == "inspect-models":
        from openbim_runner.inspect_models import MODELS_ROOT, inspect_models

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
