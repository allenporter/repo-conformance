"""Verify python project setup.cfg conformance."""

import configparser
import logging

from repo_conformance.exceptions import CheckError

from .registries import WORKTREE_CHECKS, WorktreeSpec


_LOGGER = logging.getLogger(__name__)


URL_FORMAT = "https://github.com/{user}/{repo}"


@WORKTREE_CHECKS.register()
def setupcfg(spec: WorktreeSpec) -> None:
    """Verify python project setup.cfg conformance."""

    # Verify minimal use of setup.py
    setuppy = spec.worktree / "setup.py"
    if not setuppy.exists():
        raise CheckError("Repo has no setup.py")

    contents = setuppy.read_text()
    if "setup()" not in contents:
        if "setup(" in contents:
            raise CheckError("Repo has setup.py that is not minimal")
        raise CheckError("Repo setup.py does not contain setup()")

    # Verify setup.cfg
    setupcfg = spec.worktree / "setup.cfg"
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
    if metadata["name"].replace("-", "_") != spec.repo.name.replace("-", "_"):
        raise CheckError(
            "Python project name does not match repo name: "
            f"{metadata['name']} != {spec.repo.name}"
        )
    expected_url = URL_FORMAT.format(user=spec.repo.user, repo=spec.repo.name)
    url = config["metadata"]["url"]
    if url != expected_url:
        raise CheckError(
            f"Python project url does not match repo url: {url} != {expected_url}"
        )

    if "flake8" in config:
        raise CheckError("Found flake8 config in setup.cfg; switch to ruff")
