"""Command line tool for interacting with repositories."""

import argparse
import logging
import sys
import traceback
from typing import Any

import yaml

from .list import ListAction
from .check import CheckAction


_LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Flux-local command line tool main entry point."""

    def str_presenter(dumper: yaml.Dumper, data: Any) -> Any:
        """Represent multi-line yaml strings as you'd expect.

        See https://github.com/yaml/pyyaml/issues/240
        """
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", data, style="|" if data.count("\n") > 0 else None
        )

    yaml.add_representer(str, str_presenter)

    # https://github.com/yaml/pyyaml/issues/89
    yaml.Loader.yaml_implicit_resolvers.pop("=")

    parser = argparse.ArgumentParser(
        description="Command line utility for inspecting a local flux repository.",
    )
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    )
    subparsers = parser.add_subparsers(dest="command", help="Command", required=True)

    ListAction.register(subparsers)
    CheckAction.register(subparsers)

    args = parser.parse_args()
    if args.log_level:
        logging.basicConfig(level=args.log_level)
    action = args.cls()
    try:
        action.run(**vars(args))
    except Exception as err:
        if args.log_level == "DEBUG":
            traceback.print_exc()
        print("repo error: ", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
