"""Action to list github repos for the user."""

from argparse import ArgumentParser
from argparse import _SubParsersAction as SubParsersAction
from typing import cast

from github import Github, GithubException

from .manifest import parse_manifest


class ListReposAction:
    """List action."""

    @classmethod
    def register(
        cls, subparsers: SubParsersAction  # type: ignore[type-arg]
    ) -> ArgumentParser:
        args = cast(
            ArgumentParser,
            subparsers.add_parser("list_repos", help="List github repositories for the user.")
        )
        args.set_defaults(cls=ListReposAction)
        return args

    def run(  # type: ignore[no-untyped-def]
        self,
        **kwargs,  # pylint: disable=unused-argument
    ) -> None:
        """Async Action implementation."""
        manifest = parse_manifest()
        manifest_repos = {
            repo.name: repo
            for repo in manifest.repos
        }
        ignored_manifest_repos = {
            repo.name: repo
            for repo in manifest.ignored_repos
        }
        github = Github()
        

        for repo in github.get_user(manifest.user).get_repos():
            if repo.fork or repo.archived or repo.private:
                continue
            if repo.name in ignored_manifest_repos:
                continue
            prefix = "  "
            if repo.name in manifest_repos:
                prefix = "* "
            print(f"{prefix}name: {repo.name} user: {repo.owner.login}")
