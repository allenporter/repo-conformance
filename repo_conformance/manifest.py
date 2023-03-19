"""Library for parsing the manifest."""

import pathlib
from pydantic import BaseModel, Field
import yaml


MANIFEST = pathlib.Path("manifest.yaml")


class Repo(BaseModel):
    """git repo representation."""

    name: str
    """Name of the repository."""

    user: str | None = None
    """Name of the repository owner, otherwise uses default in manifest."""


class Manifest(BaseModel):
    """Repo manifest."""

    user: str
    """Default git username that owns the repositories."""

    repos: list[Repo] = Field(default_factory=[])


def parse_manifest() -> Manifest:
    """Read the manifest file into an object."""
    with open(MANIFEST) as fd:
        doc = yaml.load(fd, Loader=yaml.CLoader)
    return Manifest.parse_obj(doc)
