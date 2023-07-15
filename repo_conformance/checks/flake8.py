"""Verify flake8 conformance."""

import configparser
import logging
import pathlib

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS


_LOGGER = logging.getLogger(__name__)


URL_FORMAT = "https://github.com/{user}/{repo}"


@WORKTREE_CHECKS.register(default=False)
def flake8(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify python project setup.cfg conformance."""

    setupcfg = worktree / "setup.cfg"
    if not setupcfg.exists:
        raise CheckError("Repo has no setup.cfg")

    config = configparser.ConfigParser()
    config.read(setupcfg)
    _LOGGER.debug("setup.cfg: %s", dict(config))

    if not config.has_section("flake8"):
        raise CheckError("flake8 configuration missing from setup.cfg")

    if config.has_option("flake8", "ignore"):
        ignore = config["flake8"]["ignore"]
        if "#" in ignore:
            raise CheckError(f"flake8 ignore content has invalid format: {ignore}")
