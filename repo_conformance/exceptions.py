"""Module for exceptions related to conformance checks."""

from dataclasses import dataclass, field


@dataclass
class Failure:
    """An individual conformance test failure."""

    detail: str
    """A detailed error message about the check failure."""

    names: list[str] = field(default_factory=list)
    """The name of the check failure."""

    def of(self, name: str) -> "Failure":
        """Return this failure as a child nested of another check."""
        return Failure(names=[name] + self.names, detail=self.detail)

    @property
    def name(self) -> str:
        """The full failure name."""
        return "".join([f"[{name}]" for name in self.names])


class CheckError(Exception):
    """A conformance error occurred during a check."""

    def __init__(self, fail: str | Failure | list[Failure]) -> None:
        """Initialize CheckError."""
        if isinstance(fail, str):
            self._errors = [Failure(detail=fail)]
        elif isinstance(fail, Failure):
            self._errors = [fail]
        else:
            self._errors = fail

    @property
    def errors(self) -> list[Failure]:
        """Return underlying conformance errors."""
        return self._errors


class ManifestError(Exception):
    """An error parsing the manifest."""
