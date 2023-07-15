"""Verify pydantic conformance."""

import configparser
import logging
import pathlib

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS


_LOGGER = logging.getLogger(__name__)


# requirements.txt defaults to pydantic v2
WANT_DEPS = ["pydantic==2"]
AVOID_DEPS = ["pydantic==1"]
PACKAGE_FILES = [
    ".github/workflows/python-package.yaml",
    ".github/workflows/python-app.yaml",
]
# Tests also run against pydantic v1
WANT_VERSIONS = ["pydantic==1"]


@WORKTREE_CHECKS.register(default=False)
def pydantic(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify python project setup.cfg conformance."""

    setupcfg = worktree / "setup.cfg"
    if not setupcfg.exists:
        raise CheckError("Repo has no setup.cfg")

    _LOGGER.debug("Checking requirements for unwanted deps %s", AVOID_DEPS)
    requirements_files = worktree.glob("requirements*")
    requirements = [req.read_text() for req in requirements_files]
    for dep in WANT_DEPS:
        if not any(dep in content for content in requirements):
            raise CheckError(f"Missing {dep} dependencies in requirements files")
    for dep in AVOID_DEPS:
        if any(dep in content for content in requirements):
            raise CheckError(f"Found unwanted {dep} dependencies in requirements files")

    config = configparser.ConfigParser()
    config.read(setupcfg)
    _LOGGER.debug("setup.cfg: %s", dict(config))

    if "options" not in config:
        raise CheckError("setup.cfg does not have 'options'")
    options = config["options"]
    if "install_requires" not in options:
        raise CheckError(
            "setup.cfg does not have 'options.install_requires': "
            f"{list(options.items())}"
        )
    requires = options["install_requires"]
    if "pydantic" not in requires:
        raise CheckError(
            "setup.cfg 'options.install_requires' does not contain 'pydantic': "
            f"{requires}"
        )
    if "pydantic>=1" not in requires:
        raise CheckError(
            "setup.cfg 'options.install_requires' does not support 'pydantic' v1: "
            f"{requires}"
        )

    files = [worktree / file for file in PACKAGE_FILES]
    if not any([file.exists() for file in files]):
        raise CheckError(f"Repo has no {PACKAGE_FILES}")

    content = "".join([file.read_text() for file in files if file.exists()])
    for ver in WANT_VERSIONS:
        if ver not in content:
            raise CheckError(f"Missing pydantic '{ver}' in workflow {PACKAGE_FILES}")
