"""Conformance test registries."""

import pathlib
from dataclasses import dataclass

from repo_conformance.manifest import Repo
from repo_conformance.registry import CheckRegistry


REPO_CHECKS = CheckRegistry[Repo]()
"""Root conformance test registry for a manifest.Repo."""


@dataclass
class WorktreeSpec:
    """Input for a worktree based confromance test."""

    repo: Repo
    worktree: pathlib.Path

    def __str__(self) -> str:
        """Human readable name for conformance errors."""
        return str(self.repo)


WORKTREE_CHECKS = CheckRegistry[WorktreeSpec]()
"""Conformance check registry for a repository github working tree."""
