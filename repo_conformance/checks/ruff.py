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
  "hooks": [{
    "id": "ruff",
    "args": [ "--fix", "--exit-non-zero-on-fix"],
  }],
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

    requirements_files = worktree.glob("requirements*")
    requirements = [req.read_text() for req in requirements_files]
    for dep in WANT_DEPS:
        if not any(dep in content for content in requirements):
            raise CheckError(f"Missing {dep} dependencies in requirements files")
    for dep in AVOID_DEPS:
        if any(dep in content for content in requirements):
            raise CheckError(f"Found unwanted {dep} dependencies in requirements files")

    pre_commit_config = worktree / ".pre-commit-config.yaml"
    pre_commit = yaml.load(pre_commit_config.read_text(), Loader=yaml.CLoader)

    ruff_config: dict[str, Any] = next(
        iter([r for r in pre_commit.get("repos", []) if r["repo"] == PRE_COMMIT_URL]),
        None,
    ) or {}
    if ruff_config != EXPECTED_PRECOMMIT:
        diff = "\n".join(difflib.ndiff(
            yaml.dump([ruff_config], sort_keys=False).split("\n"),
            yaml.dump([EXPECTED_PRECOMMIT], sort_keys=False).split("\n")
        ))
        raise CheckError(f"Ruff pre-commit configuration mismatch:\n{diff}")
