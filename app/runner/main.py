import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openbim-runner",
        description="Run openBIM workflow checks from the command line.",
    )
    parser.add_argument(
        "workflow",
        nargs="?",
        help="Path or identifier of the workflow to run.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.workflow:
        parser.print_help()
        return 0

    print(f"Running workflow: {args.workflow}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
