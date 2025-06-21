"""Action to update a github repos using scruft."""

import pathlib
import tempfile
import logging
from contextlib import contextmanager
from argparse import ArgumentParser, BooleanOptionalAction
from collections.abc import Generator
from argparse import _SubParsersAction as SubParsersAction
from typing import cast
from subprocess import PIPE, run

import scruft
import git

from .manifest import parse_manifest, Repo

_LOGGER = logging.getLogger(__name__)

CLONE_URL_FORMAT = "https://github.com/{user}/{repo}.git"
CRUFT_BRANCH = "cruft-update"
PR_TITLE = "Apply cruft updates"
PR_BODY = "Automatically generated PR from `repo-conformance` to apply updates using `scruft`."
COMMIT_MSG = "Apply cruft updates"


@contextmanager
def repo_working_dir(
    repo: Repo, worktree: pathlib.Path | None
) -> Generator[git.Repo, None, None]:
    """Open the repository locally."""
    if worktree:
        yield git.Repo.init(worktree)
        return

    # Checkout the repo locally
    with tempfile.TemporaryDirectory() as tmpdir:
        git_repo = git.Repo.init(tmpdir)
        origin = git_repo.create_remote(
            "origin", CLONE_URL_FORMAT.format(user=repo.user, repo=repo.name)
        )
        if not origin.exists():
            raise ValueError("Failure to setup repo origin")
        origin.fetch()
        if not origin.refs.main:
            raise ValueError("Git repo does not have main branch")
        main = git_repo.create_head("main", origin.refs.main)
        main.set_tracking_branch(origin.refs.main)
        main.checkout()

        yield git_repo


def verify_gh_auth() -> None:
    """Verify the user is logged into the Github CLI."""
    _LOGGER.debug("Verifying user is logged into Github CLI")
    result = run(
        ["gh", "auth", "status"],
        check=True,
        stdout=PIPE,
        stderr=PIPE,
    )
    _LOGGER.debug("gh auth status: %s", result.stdout.decode())


def create_cruft_branch(git_repo: git.Repo) -> None:
    """Create a branch for the cruft update."""
    _LOGGER.debug("Creating a branch for the cruft update")
    branch = git_repo.create_head(CRUFT_BRANCH)
    branch.checkout()
    if git_repo.active_branch.name != CRUFT_BRANCH:
        raise ValueError(
            f"Local clone of repository is not tracking cruft-update branch: {git_repo.active_branch.name}"
        )


def apply_updates(git_repo: git.Repo) -> None:
    """Perform cruft updates in the github repository."""
    _LOGGER.debug("Applying changes from cruft")
    working_dir = pathlib.Path(git_repo.working_dir)
    if not scruft.update(working_dir):
        raise ValueError("Cruft update failed")


def commit_changes(git_repo: git.Repo, comit_message: str) -> None:
    """Commit changes to the branch."""
    git_repo.git.add(update=True)
    if git_repo.untracked_files:
        git_repo.git.add(git_repo.untracked_files)
    git_repo.index.commit(comit_message)


def push_and_create_pr(git_repo: git.Repo, dry_run: bool = False) -> str:
    git_repo.remote().push(refspec=f"{CRUFT_BRANCH}:{CRUFT_BRANCH}", force=True)
    _LOGGER.info("Branch '%s' pushed to remote.", CRUFT_BRANCH)
    _LOGGER.info("Creating PR")
    result = run(
        [
            "gh",
            "pr",
            "create",
            "--title",
            PR_TITLE,
            "--body",
            PR_BODY,
            "--head",
            CRUFT_BRANCH,
            "--base",
            "main",
        ],
        cwd=str(git_repo.working_dir),
        stdout=PIPE,
        stderr=PIPE,
    )
    if result.returncode != 0:
        raise ValueError(
            "Error when creating PR with `gh pr create`: " + result.stderr.decode()
        )
    return result.stdout.decode()


class UpdateRepoAction:
    """Update repo action."""

    @classmethod
    def register(cls, subparsers: SubParsersAction) -> ArgumentParser:
        args = cast(
            ArgumentParser,
            subparsers.add_parser("update_repo", help="Update a github repository."),
        )
        args.add_argument(
            "repo",
            help="The name of the repo to check, or all if omitted",
            type=str,
            nargs="?",
        )
        args.add_argument(
            "--worktree",
            help="The local worktree path to use instead of cloning the repo",
            type=pathlib.Path,
            required=False,
        )
        args.add_argument(
            "--dry-run",
            help="Run without pushing and sending a PR.",
            type=str,
            default=False,
            action=BooleanOptionalAction,
        )
        args.set_defaults(cls=UpdateRepoAction)
        return args

    def run(  # type: ignore[no-untyped-def]
        self,
        repo: str,
        worktree: pathlib.Path | None = None,
        dry_run: bool = False,
        **kwargs,  # pylint: disable=unused-argument
    ) -> None:
        """Async Action implementation."""
        manifest = parse_manifest()
        # Before attempting to send a PR make sure we're able to leverage gh credentials
        verify_gh_auth()

        projects = 0
        updated = 0
        already_up_to_date = 0

        for manifest_repo in manifest.repos:
            if "cruft" not in manifest_repo.checks.include:
                _LOGGER.info(
                    "Skipping repo %s; cruft not in include checks.", manifest_repo
                )
                continue
            if repo and manifest_repo.name != repo:
                continue
            if not manifest_repo.user:
                manifest_repo.user = manifest.user

            print(f"Updating repo: {manifest_repo}")
            with repo_working_dir(manifest_repo, worktree) as git_repo:
                if git_repo.is_dirty() or git_repo.untracked_files:
                    raise ValueError(
                        "Local clone of repository is dirty or has untracked files"
                    )

                projects += 1
                create_cruft_branch(git_repo)
                apply_updates(git_repo)
                if not git_repo.is_dirty():
                    already_up_to_date += 1
                    _LOGGER.info(
                        "No changes detected after scruft update; Repo is up to date."
                    )
                    continue
                updated += 1

                commit_changes(git_repo, COMMIT_MSG)
                if dry_run:
                    print("Dry run complete. Changes applied locally.")
                    continue

                url = push_and_create_pr(git_repo)
                print(f"Created pull request: {url}")

        print(
            f"Updated {updated} of {projects} projects ({already_up_to_date} already up to date)."
        )
