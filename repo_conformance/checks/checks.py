"""Checks for the repository."""

from collections.abc import Callable
import logging

from ..manifest import Repo


_LOGGER = logging.getLogger(__name__)


class CheckError(Exception):
    """A conformance error occurred during a check."""


Check = Callable[[Repo], None]


class CheckRegistry:
    """Registry for all check implementations."""

    registry = {}

    @classmethod
    def register(cls, name: str) -> Callable[[Check], Check]:
        """Class method to register a check."""

        def wrapper(wrapped_class: Check) -> Check:
            cls.registry[name] = wrapped_class
            return wrapped_class

        return wrapper


def check_repo(repo: Repo) -> list[CheckError]:
    """Run checks."""
    _LOGGER.debug("Checking %s", repo.name)
    errors = []
    for name, check in CheckRegistry.registry.items():
        _LOGGER.debug("Checking %s on %s", name, repo.name)
        try:
            check(repo)
        except CheckError as err:
            errors.append(CheckError(f"[{repo.name}] [{name}] {err}"))
    return errors
