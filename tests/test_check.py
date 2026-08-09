"""Tests for CheckAction and conformance checks."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from repo_conformance.check import CheckAction
from repo_conformance.checks.cruft import get_latest_commit
from repo_conformance.checks.worktree import fetch_remote_cruft_config
from repo_conformance.exceptions import CheckError
from repo_conformance.manifest import CheckContext, Manifest, Repo


class FakeHttpResponse:
    """Fake HTTP response object for urlopen."""

    def __init__(self, content: bytes, status: int = 200) -> None:
        self.status = status
        self._content = content

    def read(self) -> bytes:
        return self._content

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, *args: object) -> None:
        pass


def test_fetch_remote_cruft_config_success() -> None:
    """Test fetching remote .cruft.json content."""
    mock_content = b'{"template": "cookiecutter-python", "commit": "123"}'
    fake_resp = FakeHttpResponse(mock_content)

    with patch("urllib.request.urlopen", return_value=fake_resp):
        res = fetch_remote_cruft_config("allenporter", "ical")
        assert res == mock_content


def test_fetch_remote_cruft_config_failure() -> None:
    """Test handling of HTTP error when fetching remote .cruft.json."""
    with patch("urllib.request.urlopen", side_effect=OSError("Network error")):
        with pytest.raises(CheckError, match="Failed to fetch .cruft.json"):
            fetch_remote_cruft_config("allenporter", "nonexistent")


def test_get_latest_commit_caching() -> None:
    """Test that get_latest_commit caches results."""
    mock_res = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="abc123456789\trefs/heads/main\n"
    )

    with patch("subprocess.run", return_value=mock_res) as mock_run:
        commit1 = get_latest_commit("allenporter/test-template")
        commit2 = get_latest_commit("allenporter/test-template")
        assert commit1 == "abc123456789"
        assert commit2 == "abc123456789"
        # Verify subprocess.run was only called once due to @cache
        mock_run.assert_called_once()


def test_check_action_worktree_validation() -> None:
    """Test that specifying --worktree without repo raises ValueError."""
    action = CheckAction()
    with pytest.raises(
        ValueError, match="Cannot specify --worktree without a single repo"
    ):
        action.run(repo=None, worktree=Path("/tmp/test"))


def test_check_action_runs_fast_cruft(tmp_path: Path) -> None:
    """Test CheckAction running against a mock repo."""
    action = CheckAction()
    cruft_file = tmp_path / ".cruft.json"
    cruft_file.write_text(
        json.dumps({
            "template": "https://github.com/allenporter/cookiecutter-python",
            "commit": "abc1234",
        })
    )

    repo = Repo(name="ical", user="allenporter")
    fake_manifest = Manifest(
        user="allenporter",
        repos=[repo],
        checks=CheckContext(),
    )

    with (
        patch(
            "repo_conformance.check.parse_manifest", return_value=fake_manifest
        ),
        patch(
            "repo_conformance.checks.cruft.get_latest_commit",
            return_value="abc1234",
        ),
    ):
        # Run check on local worktree
        action.run(repo="ical", worktree=tmp_path, include=["cruft"])
