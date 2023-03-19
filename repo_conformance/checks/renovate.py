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
        raise CheckError("No renovate.json5 configuration file found")

    renovate = json5.loads(config_file.read_text())

    extends = renovate.get(EXTENDS, [])
    if extends != EXPECTED_EXTENDS:
        diff = "\n".join(
            difflib.ndiff(
                json.dumps({EXTENDS: extends}, sort_keys=False).split("\n"),
                json.dumps({EXTENDS: EXPECTED_EXTENDS}, sort_keys=False).split("\n"),
            )
        )
        raise CheckError(f"Renovate 'extends' configuration mismatch:\n{diff}")

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
