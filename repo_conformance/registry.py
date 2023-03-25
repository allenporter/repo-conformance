"""A library to create a registry of conformance checks.

This is generic in that it can support different types of inputs/outputs
so that you can have checks at various levels (e.g. reusing state).
"""

from collections.abc import Callable
import logging
from typing import TypeVar, Generic

from .exceptions import CheckError, Failure
from .manifest import Repo


_LOGGER = logging.getLogger(__name__)


T = TypeVar("T")
Check = Callable[[Repo, T], None]


class CheckRegistry(Generic[T]):
    """Registry for check implementations.

    Typically using includes instantiating an instance of this object
    to register a specific type of check, then adding a decorator of
    the register method for each check.
    """

    def __init__(self) -> None:
        """Initialize a CheckRegistry."""
        self._registry = {}

    def register(self) -> Callable[[Check[T]], Check[T]]:
        """Class method to register a check."""

        def wrapper(wrapped_class: Check[T]) -> Check:
            if wrapped_class.__name__ in self._registry:
                raise ValueError(
                    "Misconfiguration with duplicate registry entry "
                    f"'{wrapped_class.__name__}'"
                )
            self._registry[wrapped_class.__name__] = wrapped_class
            return wrapped_class

        return wrapper

    def run_checks(self, target: Repo, context: T) -> list[Failure]:
        """Run checks against the target object."""
        exclude = set(target.checks.exclude)
        _LOGGER.debug("Checking %s (exclude_checks=%s)", target, exclude)
        errors = []
        for name, check in self._registry.items():
            if name in exclude:
                continue

            _LOGGER.debug("Checking %s on %s", name, target)
            try:
                check(target, context)
            except CheckError as err:
                for error in err.errors:
                    errors.append(error.of(name))
        return errors
