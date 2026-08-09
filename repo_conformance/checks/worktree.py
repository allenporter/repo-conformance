"""Checks to perform on the contents of github repository worktree."""

import logging
import pathlib
import tempfile
import urllib.error
import urllib.request
from collections.abc import Generator
from contextlib import contextmanager

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import REPO_CHECKS, WORKTREE_CHECKS

_LOGGER = logging.getLogger(__name__)


CLONE_URL_FORMAT = "https://github.com/{user}/{repo}.git"
RAW_CRUFT_URL_FORMAT = (
    "https://raw.githubusercontent.com/{user}/{repo}/main/.cruft.json"
)


def fetch_remote_cruft_config(user: str, repo_name: str) -> bytes:
    """Fetch .cruft.json directly via raw HTTP to avoid full git fetch overhead."""
    url = RAW_CRUFT_URL_FORMAT.format(user=user, repo=repo_name)
    req = urllib.request.Request(url, headers={"User-Agent": "repo-conformance"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.read()
    except urllib.error.HTTPError as err:
        if err.code == 404:
            raise CheckError(
                f"Repo '{user}/{repo_name}' has no .cruft.json configuration file"
            ) from err
        raise CheckError(
            f"Failed to fetch .cruft.json for '{user}/{repo_name}' (HTTP {err.code}): {err}"
        ) from err
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        raise CheckError(
            f"Failed to fetch .cruft.json for '{user}/{repo_name}': {err}"
        ) from err


@contextmanager
def repo_worktree(repo: Repo) -> Generator[pathlib.Path]:
    """Open the repository locally."""
    if not repo.user:
        raise ValueError(f"Repository '{repo.name}' missing user configuration")

    with tempfile.TemporaryDirectory() as worktree:
        worktree_path = pathlib.Path(worktree)
        cruft_bytes = fetch_remote_cruft_config(repo.user, repo.name)
        (worktree_path / ".cruft.json").write_bytes(cruft_bytes)
        yield worktree_path


@REPO_CHECKS.register()
def worktree(repo: Repo, target: None) -> None:
    """Run conformance tests on the github worktree."""

    if repo.worktree:
        errors = WORKTREE_CHECKS.run_checks(repo, context=pathlib.Path(repo.worktree))
    else:
        with repo_worktree(repo) as worktree:
            errors = WORKTREE_CHECKS.run_checks(repo, context=worktree)
    if errors:
        raise CheckError(errors)
