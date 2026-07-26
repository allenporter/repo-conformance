"""Tests for manifest parsing, data structures, and error handling."""

from unittest.mock import mock_open, patch

import pytest

from repo_conformance.exceptions import ManifestError
from repo_conformance.manifest import CheckContext, Repo, parse_manifest


def test_parse_manifest() -> None:
    """Test parsing the current manifest in the repo."""

    manifest = parse_manifest()
    assert manifest.user == "allenporter"
    assert len(manifest.repos) > 0


def test_repo_str_representation() -> None:
    """Test Repo string formatting."""
    repo = Repo(name="icaldav", user="allenporter")
    assert str(repo) == "allenporter/icaldav"


def test_check_context_defaults() -> None:
    """Test CheckContext defaults."""
    ctx = CheckContext()
    assert ctx.exclude == []
    assert ctx.include == []


def test_parse_manifest_invalid_yaml_raises_error() -> None:
    """Test that invalid YAML syntax in manifest.yaml raises ManifestError."""
    invalid_yaml = "user: allenporter\nrepos: [unclosed_list"
    with patch("builtins.open", mock_open(read_data=invalid_yaml)):
        with pytest.raises(ManifestError) as exc_info:
            parse_manifest()
        assert "Unable to parse manifest" in str(exc_info.value)
