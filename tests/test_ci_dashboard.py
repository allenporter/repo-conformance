"""Tests for CiAction and DashboardAction logic and export behavior."""

from unittest.mock import MagicMock, patch

from repo_conformance.ci import CiAction, get_run_status
from repo_conformance.dashboard import DashboardAction
from repo_conformance.manifest import Manifest, Repo
from repo_conformance.prs import GitHubClient


class FakeGitHubClient(GitHubClient):
    """Fake GitHub client for deterministic unit testing."""

    def __init__(self, prs_by_repo: dict[str, list[dict]] | None = None) -> None:
        self.prs_by_repo = prs_by_repo or {}
        self.authenticated = True

    def check_auth(self) -> bool:
        return self.authenticated

    def list_prs(self, repo_fullname: str) -> list[dict]:
        return self.prs_by_repo.get(repo_fullname, [])


def test_get_run_status_formatting() -> None:
    """Test get_run_status color and uncolored output."""
    passed_run = {"status": "completed", "conclusion": "SUCCESS"}
    failed_run = {"status": "completed", "conclusion": "FAILURE"}
    in_prog_run = {"status": "in_progress", "conclusion": None}

    assert "PASSED" in get_run_status(passed_run, color=False)
    assert "FAILED" in get_run_status(failed_run, color=False)
    assert "IN_PROGRESS" in get_run_status(in_prog_run, color=False)


@patch("repo_conformance.ci.parse_manifest")
@patch("subprocess.run")
def test_ci_action_execution(
    mock_subproc_run: MagicMock,
    mock_parse_manifest: MagicMock,
) -> None:
    """Test CiAction run output parsing."""
    mock_manifest = Manifest(
        user="allenporter", repos=[Repo(name="test-repo", user="allenporter")]
    )
    mock_parse_manifest.return_value = mock_manifest

    fake_res = MagicMock()
    fake_res.returncode = 0
    fake_res.stdout = '[{"name": "CI", "status": "completed", "conclusion": "SUCCESS", "event": "push", "createdAt": "2026-08-09T12:00:00Z"}]'
    mock_subproc_run.return_value = fake_res

    fake_client = FakeGitHubClient()
    action = CiAction()

    with patch("builtins.print") as mock_print:
        action.run(repo=None, client=fake_client)
        printed_lines = [
            call.args[0] for call in mock_print.call_args_list if call.args
        ]
        assert any("test-repo" in str(line) for line in printed_lines)
        assert any("PASSED" in str(line) for line in printed_lines)


@patch("repo_conformance.dashboard.parse_manifest")
@patch("repo_conformance.dashboard.get_latest_commit")
@patch("subprocess.run")
def test_dashboard_action_execution_and_export(
    mock_subproc_run: MagicMock,
    mock_get_latest_commit: MagicMock,
    mock_parse_manifest: MagicMock,
    tmp_path,
) -> None:
    """Test DashboardAction execution and markdown file export."""
    mock_manifest = Manifest(
        user="allenporter", repos=[Repo(name="test-repo", user="allenporter")]
    )
    mock_parse_manifest.return_value = mock_manifest
    mock_get_latest_commit.return_value = "abc1234567890"

    fake_res = MagicMock()
    fake_res.returncode = 0
    fake_res.stdout = '[{"status": "completed", "conclusion": "SUCCESS"}]'
    mock_subproc_run.return_value = fake_res

    fake_client = FakeGitHubClient({"allenporter/test-repo": []})
    action = DashboardAction()
    export_file = tmp_path / "REPOS_HEALTH.md"

    action.run(export=export_file, client=fake_client)

    assert export_file.exists()
    content = export_file.read_text(encoding="utf-8")
    assert "# Repository Health Dashboard" in content
    assert "`test-repo`" in content
