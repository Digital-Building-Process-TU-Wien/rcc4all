from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

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
    return parser


def normalize_argv(argv: Sequence[str] | None) -> list[str]:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"run", "export-schema", "-h", "--help"}:
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

    workflow_path = Path(args.workflow).resolve()

    try:
        node_outputs = execute_workflow(workflow_path)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(error)
        return 1

    print(dump_results(node_outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
