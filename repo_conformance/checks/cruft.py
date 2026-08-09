"""Conformance tests to for ensuring the repository is up to date."""

import json
import logging
import os
import pathlib
import subprocess
from functools import cache

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS

_LOGGER = logging.getLogger(__name__)


@cache
def get_latest_commit(repo_full_name: str) -> str:
    """Get the latest commit hash for a given repository."""
    url = f"https://github.com/{repo_full_name}.git"
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        res = subprocess.run(
            ["git", "ls-remote", url, "refs/heads/main"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
        if res.stdout:
            return res.stdout.split()[0]
        raise CheckError(f"No commit ref found for main branch of '{repo_full_name}'")
    except (subprocess.SubprocessError, OSError) as err:
        raise CheckError(
            f"git ls-remote failed for template '{repo_full_name}': {err}"
        ) from err


@WORKTREE_CHECKS.register(default=False)
def cruft(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify the github repository configuration via the github API."""
    cruft_file = worktree / ".cruft.json"
    if not cruft_file.exists():
        raise CheckError("Repo has no .cruft.json configuration file")

    with cruft_file.open("r") as fd:
        cruft_config = json.load(fd)

    template_url = cruft_config["template"].rstrip("/")
    repo_full_name = "/".join(template_url.split("/")[-2:])
    commit = cruft_config["commit"]
    try:
        latest_commit = get_latest_commit(repo_full_name)
    except Exception as err:
        raise CheckError(
            f"Failed to retrieve latest commit for template '{repo_full_name}': {err}"
        ) from err

    if commit != latest_commit:
        raise CheckError(f"Repo is out of date, expected {latest_commit}, got {commit}")
