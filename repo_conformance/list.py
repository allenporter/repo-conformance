"""Action to list contents of the manifest."""

from argparse import ArgumentParser
from argparse import _SubParsersAction as SubParsersAction
from typing import cast

from .manifest import parse_manifest


class ListAction:
    """List action."""

    @classmethod
    def register(
        cls, subparsers: SubParsersAction  # type: ignore[type-arg]
    ) -> ArgumentParser:
        args = cast(
            ArgumentParser,
            subparsers.add_parser("list", help="List repositories in the manifest")
        )
        args.set_defaults(cls=ListAction)
        return args

    def run(  # type: ignore[no-untyped-def]
        self,
        **kwargs,  # pylint: disable=unused-argument
    ) -> None:
        """Async Action implementation."""
        manifest = parse_manifest()
        for repo in manifest.repos:
            print(f"name: {repo.name} user: {repo.user or manifest.user}")
