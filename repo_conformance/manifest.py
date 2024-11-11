"""Library for parsing the manifest."""

import pathlib
from dataclasses import dataclass, field
from typing import Any

from mashumaro.codecs.yaml import yaml_decode
from mashumaro import DataClassDictMixin
import yaml

from .exceptions import ManifestError


MANIFEST = pathlib.Path("manifest.yaml")


@dataclass
class CheckContext(DataClassDictMixin):
    """Context for a specific check."""

    exclude: list[str] = field(default_factory=list)
    """Conformance tests to exclude."""

    include: list[str] = field(default_factory=list)
    """Non-default conformance tests to include."""

    def allow_empty(cls, value: Any | None) -> Any:
        return value or []


@dataclass
class Repo(DataClassDictMixin):
    """git repo representation."""

    name: str
    """Name of the repository."""

    user: str | None = None
    """Name of the repository owner, otherwise uses default in manifest."""

    worktree: str | None = None
    """Optional local worktree directory to use instead of a fresh clone.

    This directory will not be modified (e.g. no git pull, etc).
    """

    checks: CheckContext = field(default_factory=CheckContext)
    """Conformance test check context."""

    def __str__(self) -> str:
        """Human readable name for check output."""
        return f"{self.user}/{self.name}"


@dataclass
class IgnoredRepo(DataClassDictMixin):
    """Ignored repo representation."""

    name: str
    """Name of the repository."""


@dataclass
class Manifest(DataClassDictMixin):
    """Repo manifest."""

    user: str
    """Default git username that owns the repositories."""

    repos: list[Repo] = field(default_factory=list)

    checks: CheckContext = field(default_factory=CheckContext)
    """Conformance test check context."""

    ignored_repos: list[IgnoredRepo] = field(default_factory=list)


def parse_manifest() -> Manifest:
    """Read the manifest file into an object."""
    with open(MANIFEST) as fd:
        content = fd.read()
    try:
        return yaml_decode(content, Manifest)
    except yaml.YAMLError as err:
        raise ManifestError(f"Unable to parse manifest {MANIFEST}: {err}") from err
