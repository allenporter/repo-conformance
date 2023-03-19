"""Verifies that the repo exists in github."""

from github import Github, GithubException

from .checks import CheckRegistry, CheckError
from ..manifest import Repo


@CheckRegistry.register("exists")
def check_github(repo: Repo) -> None:
    """Verify the repo exists in github."""

    github = Github()
    full_id = f"{repo.user}/{repo.name}"
    try:
        git_repo = github.get_repo(full_id)
    except GithubException as err:
        raise CheckError(f"Github repo does not exist: {full_id}: {err}") from err

    if git_repo.has_wiki:
        raise CheckError("Repo has wiki enabled")
    if git_repo.has_projects:
        raise CheckError("Repo has projects enabled")
