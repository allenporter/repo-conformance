"""Library for parsing the manifest."""

import pathlib
from typing import Any

from pydantic import BaseModel, Field, ValidationError, validator
import yaml

from .exceptions import ManifestError


MANIFEST = pathlib.Path("manifest.yaml")


class CheckContext(BaseModel):
    """Context for a specific check."""

    exclude: list[str] = Field(default_factory=list)
    """Conformance tests to exclude."""

    @validator('exclude', pre=True)
    def allow_empty(cls, value: Any | None) -> Any:
        return value or []


class Repo(BaseModel):
    """git repo representation."""

    name: str
    """Name of the repository."""

    user: str | None = None
    """Name of the repository owner, otherwise uses default in manifest."""

    worktree: str | None = None
    """Optional local worktree directory to use instead of a fresh clone.

    This directory will not be modified (e.g. no git pull, etc).
    """

    checks: CheckContext = Field(default_factory=CheckContext)
    """Conformance test check context."""

    def __str__(self) -> str:
        """Human readable name for check output."""
        return f"{self.user}/{self.name}"


class Manifest(BaseModel):
    """Repo manifest."""

    user: str
    """Default git username that owns the repositories."""

    repos: list[Repo] = Field(default_factory=list)

    checks: CheckContext = Field(default_factory=CheckContext)
    """Conformance test check context."""


def parse_manifest() -> Manifest:
    """Read the manifest file into an object."""
    with open(MANIFEST) as fd:
        doc = yaml.load(fd, Loader=yaml.CLoader)
    try:
        return Manifest.parse_obj(doc)
    except ValidationError as err:
        raise ManifestError(f"Unable to parse manifest {MANIFEST}: {err}") from err
