"""Conformance tests to perform on the GitHub repository configuration."""

import logging

from github import Github, GithubException

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import REPO_CHECKS

_LOGGER = logging.getLogger(__name__)


@REPO_CHECKS.register()
def github(repo: Repo) -> None:
    """Verify the github repository configuration via the github API."""

    github = Github()
    full_id = f"{repo.user}/{repo.name}"
    try:
        git_repo = github.get_repo(full_id)
    except GithubException as err:
        raise CheckError(f"Github repo does not exist: {full_id}: {err}") from err
    _LOGGER.debug("Repo details: %s", git_repo)

    if git_repo.has_wiki:
        raise CheckError("Repo has wiki enabled")
    if git_repo.has_projects:
        raise CheckError("Repo has projects enabled")
