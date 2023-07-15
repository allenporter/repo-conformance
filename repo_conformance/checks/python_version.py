"""Verify github python package conformance."""

import configparser
import logging
import pathlib

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS


_LOGGER = logging.getLogger(__name__)

REQUIRES = ">= 3.9"
VERSIONS = [
    "3.9",
    "3.10",
    "3.11",
]


@WORKTREE_CHECKS.register()
def python_version(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify python version conformance."""

    setupcfg = worktree / "setup.cfg"
    if not setupcfg.exists:
        raise CheckError("Repo has no setup.cfg")

    config = configparser.ConfigParser()
    config.read(setupcfg)
    _LOGGER.debug("setup.cfg: %s", dict(config))

    if "options" not in config:
        raise CheckError("setup.cfg does not have 'options'")
    options = config["options"]
    if "python_requires" not in options:
        raise CheckError(
            "setup.cfg does not have 'options.python_requires': "
            f"{list(options.items())}"
        )
    requires = options["python_requires"]
    if requires != REQUIRES:
        raise CheckError(
            "setup.cfg 'options.python_requires' does not match: "
            f"{requires} != {REQUIRES}"
        )

    workflow = worktree / ".github/workflows/python-package.yaml"
    if not workflow.exists:
        raise CheckError("Repo has no .github/workflows/python-package.yaml")
