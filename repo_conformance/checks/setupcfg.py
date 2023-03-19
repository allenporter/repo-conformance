"""Verify python project setup.cfg conformance."""

import configparser
import logging
import pathlib

from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import Repo

from .registries import WORKTREE_CHECKS


_LOGGER = logging.getLogger(__name__)


URL_FORMAT = "https://github.com/{user}/{repo}"


@WORKTREE_CHECKS.register()
def setupcfg(repo: Repo, worktree: pathlib.Path) -> None:
    """Verify python project setup.cfg conformance."""

    setupcfg = worktree / "setup.cfg"
    if not setupcfg.exists:
        raise CheckError("Repo has no setup.cfg")

    config = configparser.ConfigParser()
    config.read(setupcfg)
    _LOGGER.debug("setup.cfg: %s", dict(config))

    if "metadata" not in config:
        raise CheckError("setup.cfg does not have 'metadata'")
    metadata = config["metadata"]
    if "name" not in metadata:
        raise CheckError("setup.cfg does not have 'metadata.name'")
    if metadata["name"].replace("-", "_") != repo.name.replace("-", "_"):
        raise CheckError(
            "Python project name does not match repo name: "
            f"{metadata['name']} != {repo.name}"
        )
    expected_url = URL_FORMAT.format(user=repo.user, repo=repo.name)
    url = config["metadata"]["url"]
    if url != expected_url:
        raise CheckError(
            f"Python project url does not match repo url: {url} != {expected_url}"
        )
