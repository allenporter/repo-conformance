"""Conformance test registries."""

import pathlib

from repo_conformance.registry import CheckRegistry


REPO_CHECKS = CheckRegistry[None]()
"""Root conformance test registry for a manifest.Repo."""

WORKTREE_CHECKS = CheckRegistry[pathlib.Path]()
"""Conformance check registry for a repository github working tree."""
