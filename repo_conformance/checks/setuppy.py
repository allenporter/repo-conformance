"""Verify python project setup.py conformance."""

import configparser
import logging
import pathlib

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS


@WORKTREE_CHECKS.register()
def setuppy(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify python project setup.py conformance."""

    # Verify minimal use of setup.py
    setuppy = worktree / "setup.py"
    if not setuppy.exists():
        raise CheckError("Repo has no setup.py")

    contents = setuppy.read_text()
    if "setup()" not in contents:
        if "setup(" in contents:
            raise CheckError("Repo has setup.py that is not minimal")
        raise CheckError("Repo setup.py does not contain setup()")
