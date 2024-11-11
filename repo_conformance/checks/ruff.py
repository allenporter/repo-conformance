"""Verify ruff conformance."""

import configparser
import difflib
import logging
import pathlib
from typing import Any
import yaml

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS


_LOGGER = logging.getLogger(__name__)

PRE_COMMIT_URL = "https://github.com/charliermarsh/ruff-pre-commit"

EXPECTED_PRECOMMIT = {
    "repo": PRE_COMMIT_URL,
    "hooks": [
        {
            "id": "ruff",
            "args": ["--fix", "--exit-non-zero-on-fix"],
        }
    ],
}

WANT_DEPS = ["ruff"]
AVOID_DEPS = ["isort", "flake8", "pylint"]


@WORKTREE_CHECKS.register()
def ruff(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify ruff conformance."""

    setupcfg = worktree / "setup.cfg"
    if not setupcfg.exists:
        raise CheckError("Repo has no setup.cfg")

    config = configparser.ConfigParser()
    config.read(setupcfg)
    if config.has_section("flake8"):
        raise CheckError("Found flake8 config in setup.cfg; switch to ruff")

    _LOGGER.debug("Checking requirements for unwanted deps %s", AVOID_DEPS)
    requirements_files = worktree.glob("requirements*")
    requirements = [req.read_text() for req in requirements_files]
    for dep in WANT_DEPS:
        if not any(dep in content for content in requirements):
            raise CheckError(f"Missing {dep} dependencies in requirements files")
    for dep in AVOID_DEPS:
        if any(dep in content for content in requirements):
            raise CheckError(f"Found unwanted {dep} dependencies in requirements files")

    pre_commit_config = worktree / ".pre-commit-config.yaml"
    if not pre_commit_config.exists():
        raise CheckError("Missing .pre-commit-config.yaml")

    pre_commit = yaml.load(pre_commit_config.read_text(), Loader=yaml.CLoader)
    pre_commit_repos = [r for r in pre_commit.get("repos", [])]

    # Ignore the repo version, and assume renovate will keep it fresh
    for repo in pre_commit_repos:
        if "rev" in repo:
            del repo["rev"]

    ruff_config: dict[str, Any] = (
        next(
            iter([r for r in pre_commit_repos if r["repo"] == PRE_COMMIT_URL]),
            None,
        )
        or {}
    )
    if ruff_config != EXPECTED_PRECOMMIT:
        diff = "\n".join(
            difflib.ndiff(
                yaml.dump([ruff_config], sort_keys=False).split("\n"),
                yaml.dump([EXPECTED_PRECOMMIT], sort_keys=False).split("\n"),
            )
        )
        raise CheckError(f"Ruff pre-commit configuration mismatch:\n{diff}")

    _LOGGER.debug("Checking pre-commit for unwanted deps %s", AVOID_DEPS)
    for dep in AVOID_DEPS:
        if any(dep in r["repo"] for r in pre_commit_repos):
            raise CheckError(f"Found unwanted {dep} dependencies in pre-commit files")

    if (worktree / ".pylintrc").exists():
        raise CheckError("Found unwanted .pylintrc")

    renovate_config = worktree / "renovate.json5"
    if renovate_config.exists():
        _LOGGER.debug("Checking renovate config for unwanted deps %s", AVOID_DEPS)
        renovate_data = renovate_config.read_text()
        for dep in AVOID_DEPS:
            if dep in renovate_data:
                raise CheckError(
                    f"Found unwanted {dep} dependencies in renovate config"
                )

    _LOGGER.debug("Checking workflows for unwanted deps %s", AVOID_DEPS)
    workflow_files = worktree.glob(".github/workflows/*")
    workflows = [req.read_text() for req in workflow_files]
    for dep in WANT_DEPS:
        if not any(dep in content for content in workflows):
            raise CheckError(f"Missing {dep} dependencies in workflows files")
    for dep in AVOID_DEPS:
        if any(dep in content for content in workflows):
            raise CheckError(f"Found unwanted {dep} dependencies in workflows files")
    if any("--format" in content for content in workflows):
        raise CheckError("Deprecated flag --format found in workflows files")
    if not any("chartboost/ruff-action@" in content for content in workflows):
        raise CheckError("Missing 'chartboost/ruff-action' in workflows files")
