"""Action to check repositories for conformance."""

from argparse import ArgumentParser
from argparse import _SubParsersAction as SubParsersAction
from typing import cast
import sys

from .manifest import parse_manifest
from .checks import checks


class CheckAction:
    """Check action."""

    @classmethod
    def register(
        cls, subparsers: SubParsersAction  # type: ignore[type-arg]
    ) -> ArgumentParser:
        args = cast(
            ArgumentParser,
            subparsers.add_parser(
                "check", help="Check repositories in the manifest for conformance"
            ),
        )
        args.add_argument
        args.add_argument(
            "repo",
            help="The name of the repo to check, or all if omitted",
            type=str,
            default=None,
            nargs="?",
        )
        args.set_defaults(cls=CheckAction)
        return args

    def run(  # type: ignore[no-untyped-def]
        self,
        repo: str | None,
        **kwargs,  # pylint: disable=unused-argument
    ) -> None:
        """Async Action implementation."""
        manifest = parse_manifest()
        errors = []
        for r in manifest.repos:
            if repo and r.name != repo:
                continue
            errors.extend(checks.check_repo(r))
        if errors:
            for error in errors:
                print(error)
            sys.exit(1)
