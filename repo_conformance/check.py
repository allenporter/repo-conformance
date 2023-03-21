"""Action to check repositories for conformance."""

from argparse import ArgumentParser
from argparse import _SubParsersAction as SubParsersAction
import logging
import re
import pathlib
import sys
from typing import cast

from .manifest import parse_manifest
from .exceptions import Failure
from .checks.registries import REPO_CHECKS


_LOGGER = logging.getLogger(__name__)


def print_errors(errors: list[Failure]) -> None:
    """Print conformance test failures."""
    for error in errors:
        indent = 0
        buf = ""
        for name in error.names:
            if indent:
                buf += "\n"
            buf += " " * indent
            buf += f"{name}:"
            indent += 2
        print(f"{buf} {error.detail}")
        print("")


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
        args.add_argument(
            "--exclude",
            help="The names of conformance tests to exclude",
            type=lambda x: re.split("[ ,]+", x),
            required=False,
            default=[],
        )
        args.add_argument(
            "--include",
            help="The names of conformance tests to include",
            type=lambda x: re.split("[ ,]+", x),
            required=False,
            default=[],
        )
        args.add_argument(
            "--worktree",
            help="The local worktree path to use instead of cloning the repo",
            type=pathlib.Path,
            required=False,
        )
        args.set_defaults(cls=CheckAction)
        return args

    def run(  # type: ignore[no-untyped-def]
        self,
        repo: str | None,
        exclude: list[str] | None = None,
        include: list[str] | None = None,
        worktree: pathlib.Path | None = None,
        **kwargs,  # pylint: disable=unused-argument
    ) -> None:
        """Async Action implementation."""
        if worktree and not repo:
            raise ValueError("Cannot specify --worktree without a single repo argument")
        if exclude:
            _LOGGER.debug("Excluding checks: %s", exclude)
        manifest = parse_manifest()
        errors = []
        for r in manifest.repos:
            if repo and r.name != repo:
                continue
            if not r.user:
                r.user = manifest.user
            r.checks.exclude = list(
                (set(r.checks.exclude) | set(manifest.checks.exclude) | set(exclude)) - set(include)
            )
            if worktree:
                r.worktree = worktree

            errors.extend([fail.of(r.name) for fail in REPO_CHECKS.run_checks(r, None)])
        if errors:
            print_errors(errors)
            sys.exit(1)
