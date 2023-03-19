"""Verify ruff conformance."""

import configparser
import logging
import pathlib
from typing import Any
import yaml

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS


_LOGGER = logging.getLogger(__name__)

PRE_COMMIT_URL = "https://github.com/charliermarsh/ruff-pre-commit"
EXPECTED_HOOKS = [{"id": "ruff"}]


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
    if not any("ruff==" in req.read_text() for req in requirements_files):
        raise CheckError("Missing ruff dependencies in requirements files")
    # TODO: Add additional ruff setup conformance tests

    pre_commit_config = worktree / ".pre-commit-config.yaml"
    pre_commit = yaml.load(pre_commit_config.read_text(), Loader=yaml.CLoader)

    ruff_config: dict[str, Any] | None = next(
        iter([r for r in pre_commit.get("repos", []) if r["repo"] == PRE_COMMIT_URL]),
        None,
    )
    if not ruff_config:
        raise CheckError("Missing ruff pre-commit configuration")
    if ruff_config.get("hooks", []) != EXPECTED_HOOKS:
        raise CheckError(
            f"Ruff hooks configuration mismatch: {ruff_config.get('hooks')} "
            f"!= {EXPECTED_HOOKS}"
        )
