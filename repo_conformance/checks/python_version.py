"""Verify github python package conformance."""

import configparser
import logging
import pathlib

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS


_LOGGER = logging.getLogger(__name__)

REQUIRES = [">=3.10", ">=3.11"]
WANT_VERSIONS = [
    [
        "3.10",
        "3.11",
    ],
    [
        "3.11",
    ],
]
AVOID_VERSIONS = ["3.7", "3.8", "3.9"]
TEST_FILES = [
    ".github/workflows/python-package.yaml",
    ".github/workflows/python-app.yaml",
    ".github/workflows/test.yaml",
]


@WORKTREE_CHECKS.register()
def python_version(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify python version conformance."""

    setupcfg = worktree / "setup.cfg"
    if not setupcfg.exists():
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
    if not any(req in requires for req in REQUIRES):
        raise CheckError(
            "setup.cfg 'options.python_requires' does not match: "
            f"{requires} != {REQUIRES}"
        )

    files = [worktree / file for file in TEST_FILES]
    if not any([file.exists() for file in files]):
        raise CheckError(f"Repo has no {TEST_FILES}")

    content = "".join([file.read_text() for file in files if file.exists()])
    for ver_sets in WANT_VERSIONS:
        if not any(ver in content for ver in ver_sets):
            raise CheckError(f"Missing python '{ver_sets}' in workflow {TEST_FILES}")
    for ver in AVOID_VERSIONS:
        if ver in content:
            raise CheckError(f"Found unwanted python '{ver}' in workflow {TEST_FILES}")
