
"""Conformance tests to for ensuring the repository is up to date."""

import logging
import json
import pathlib
from functools import cache

from github import Github, GithubException

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS

_LOGGER = logging.getLogger(__name__)


@cache
def get_latest_commit(repo_full_name: str) -> str:
    """Get the latest commit hash for a given repository."""
    github = Github()
    repo = github.get_repo(repo_full_name)
    commits = repo.get_commits()
    return next(iter(commits)).sha


@WORKTREE_CHECKS.register(default=False)
def cruft(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify the github repository configuration via the github API."""
    cruft_file = worktree / ".cruft.json"
    if not cruft_file.exists():
        raise CheckError("Repo has no .cruft.json configuration file")

    with cruft_file.open("r") as fd:
        cruft_config = json.load(fd)

    template_url = cruft_config["template"]
    repo_full_name = "/".join(template_url.split("/")[-2:])
    commit = cruft_config["commit"]
    latest_commit = get_latest_commit(repo_full_name)
    if commit != latest_commit:
        raise CheckError(
            f"Repo is out of date, expected {latest_commit}, got {commit}"
        )
