"""Verify pydantic conformance."""

import configparser
import logging
import pathlib

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS


_LOGGER = logging.getLogger(__name__)


URL_FORMAT = "https://github.com/{user}/{repo}"


@WORKTREE_CHECKS.register(default=False)
def pydantic(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify python project setup.cfg conformance."""

    setupcfg = worktree / "setup.cfg"
    if not setupcfg.exists:
        raise CheckError("Repo has no setup.cfg")

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
