"""Checks to perform on the contents of github repository worktree."""

from collections.abc import Generator
from contextlib import contextmanager
import logging
import pathlib
import tempfile

import git

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import REPO_CHECKS, WORKTREE_CHECKS


_LOGGER = logging.getLogger(__name__)


CLONE_URL_FORMAT = "https://github.com/{user}/{repo}.git"


@contextmanager
def repo_worktree(repo: Repo) -> Generator[pathlib.Path, None, None]:
    """Open the repository locally."""
    with tempfile.TemporaryDirectory() as worktree:
        git_repo = git.Repo.init(worktree)
        origin = git_repo.create_remote(
            "origin", CLONE_URL_FORMAT.format(user=repo.user, repo=repo.name)
        )
        if not origin.exists():
            raise CheckError("Failure to setup repo origin")

        origin.fetch()

        if not origin.refs.main:
            raise CheckError("Git repo does not have main branch")
        main = git_repo.create_head("main", origin.refs.main)
        main.set_tracking_branch(origin.refs.main)
        main.checkout()

        if git_repo.is_dirty():
            raise CheckError("Local clone of repository is dirty")
        if git_repo.untracked_files:
            raise CheckError("Local clone of repository has untracked files")

        yield pathlib.Path(worktree)


@REPO_CHECKS.register()
def worktree(repo: Repo, target: None) -> None:
    """Run conformance tests on the github worktree."""

    with repo_worktree(repo) as worktree:
        errors = WORKTREE_CHECKS.run_checks(repo, context=worktree)
        if errors:
            raise CheckError(errors)
