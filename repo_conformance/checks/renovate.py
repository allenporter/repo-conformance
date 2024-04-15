"""Verify renovate conformance."""

import difflib
import logging
import pathlib
import json
import json5

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS


_LOGGER = logging.getLogger(__name__)

PRE_COMMIT_URL = "https://github.com/charliermarsh/ruff-pre-commit"
EXTENDS = "extends"
EXPECTED_EXTENDS = [
    "config:base",
]
ASSIGNEES = "assignees"
PRECOMMIT = "pre-commit"
EXPECTED_PRECOMMIT = {"enabled": True}


@WORKTREE_CHECKS.register()
def renovate(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify renovate conformance."""

    plain_config_file = worktree / "renovate.json"
    if plain_config_file.exists():
        raise CheckError("Found renovate.json but prefer renovate.json5")

    config_file = worktree / "renovate.json5"
    if not config_file.exists():
        config_file = worktree / ".github" / "renovate.json5"
        if not config_file.exists():
            raise CheckError("No renovate.json5 configuration file found")

    renovate = json5.loads(config_file.read_text())

    extends = set(renovate.get(EXTENDS, []))
    expected = set(EXPECTED_EXTENDS)
    extends_expected = extends | expected
    if extends != extends_expected:
        diff = "\n".join(
            difflib.ndiff(
                json.dumps({EXTENDS: extends}, sort_keys=False).split("\n"),
                json.dumps({EXTENDS: extends_expected}, sort_keys=False).split("\n"),
            )
        )
        raise CheckError(f"Renovate 'extends' configuration mismatch:\n{diff}")

    assignees = renovate.get(ASSIGNEES, [])
    if repo.user not in assignees:
        diff = "\n".join(
            difflib.ndiff(
                json.dumps({ASSIGNEES: assignees}, sort_keys=False).split("\n"),
                json.dumps({ASSIGNEES: assignees + [repo.user]}, sort_keys=False).split(
                    "\n"
                ),
            )
        )
        raise CheckError(f"Renovate 'assignees' configuration mismatch:\n{diff}")

    precommit = renovate.get(PRECOMMIT, [])
    if precommit != EXPECTED_PRECOMMIT:
        diff = "\n".join(
            difflib.ndiff(
                json.dumps({PRECOMMIT: precommit}, sort_keys=False).split("\n"),
                json.dumps({PRECOMMIT: EXPECTED_PRECOMMIT}, sort_keys=False).split(
                    "\n"
                ),
            )
        )
        raise CheckError(f"Renovate 'pre-commit' configuration mismatch:\n{diff}")

    if "assignees" not in renovate:
        raise CheckError("Renovate had no default 'assignees' field")

    if "dependencyDashboard" in renovate:
        raise CheckError("Renovate 'dependencyDashboard' is unnecessary")
