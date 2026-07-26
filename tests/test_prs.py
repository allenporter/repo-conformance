"""Tests for PR status logic, SemVer boundary guard, security update detection, and filtering strictness using Fakes."""

from unittest.mock import MagicMock, patch

import pytest

from repo_conformance.manifest import Manifest, Repo
from repo_conformance.prs import (
    GitHubClient,
    PrsAction,
    is_major_version_bump,
    is_security_update,
)


class FakeGitHubClient(GitHubClient):
    """Fake GitHub client for deterministic unit testing without subprocess mocks."""

    def __init__(self, prs_by_repo: dict[str, list[dict]] | None = None) -> None:
        self.prs_by_repo = prs_by_repo or {}
        self.merged_prs: list[tuple[str, int]] = []
        self.authenticated = True

    def check_auth(self) -> bool:
        return self.authenticated

    def list_prs(self, repo_fullname: str) -> list[dict]:
        return self.prs_by_repo.get(repo_fullname, [])

    def get_pr_diff_files(self, repo_fullname: str, pr_number: int) -> list[str]:
        for pr in self.list_prs(repo_fullname):
            if pr.get("number") == pr_number:
                return pr.get("mock_diff_files", [])
        return []

    def get_pr_checks(self, repo_fullname: str, pr_number: int) -> str:
        return "All checks passed"

    def merge_pr(self, repo_fullname: str, pr_number: int) -> tuple[bool, str]:
        self.merged_prs.append((repo_fullname, pr_number))
        return True, ""


def test_is_major_version_bump_titles() -> None:
    """Test detecting major version bumps from PR titles and bodies."""

    # Major version bumps
    assert is_major_version_bump("Update dependency pytest to v8")
    assert is_major_version_bump("Update module github.com/foo/bar to v2")
    assert is_major_version_bump("Bumps pytest from 7.4.0 to 8.0.0")
    assert is_major_version_bump("chore(deps): update major dependency pydantic to v2")
    assert is_major_version_bump(
        "Update dependency foo", "Bumps foo from 1.10.0 to 2.0.0"
    )

    # Minor / Patch bumps (not major)
    assert not is_major_version_bump("Update dependency ruff to v0.9.0")
    assert not is_major_version_bump("Bumps pytest from 8.1.0 to 8.2.0")
    assert not is_major_version_bump("Bumps pytest from 8.3.1 to 8.3.2")
    assert not is_major_version_bump("chore: accept new Cruft update")


def test_is_security_update() -> None:
    """Test detecting security update PRs."""

    assert is_security_update("Security fix for urllib3 CVE-2024-1234")
    assert is_security_update(
        "Bump requests to 2.32.0", "Fixes high severity vulnerability"
    )
    assert is_security_update("Security advisory fix")

    assert not is_security_update("Update dependency ruff to v0.9.0")
    assert not is_security_update("chore: accept new Cruft update")


# Real-world PR payload scenarios
MOCK_PRS_PAYLOAD = [
    # 1. Renovate patch PR (Ready to merge)
    {
        "number": 101,
        "title": "Update dependency ruff to v0.9.0",
        "author": {"login": "renovate[bot]", "is_bot": True},
        "createdAt": "2026-07-25T12:00:00Z",
        "headRefName": "renovate/ruff-0.x",
        "reviewDecision": "",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "isDraft": False,
        "body": "Bumps ruff from 0.8.0 to 0.9.0",
        "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
    },
    # 2. Renovate major PR (Ready CI, but Major bump)
    {
        "number": 102,
        "title": "Update dependency pytest to v8",
        "author": {"login": "renovate[bot]", "is_bot": True},
        "createdAt": "2026-07-25T12:00:00Z",
        "headRefName": "renovate/pytest-8.x",
        "reviewDecision": "",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "isDraft": False,
        "body": "Bumps pytest from 7.4.0 to 8.0.0",
        "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
    },
    # 3. Self-authored feature PR (Ready CI, but self-authored feature)
    {
        "number": 201,
        "title": "feat(client): add OAuth 2.0 authorization code flow",
        "author": {"login": "allenporter", "is_bot": False},
        "createdAt": "2026-07-25T12:00:00Z",
        "headRefName": "oauth-support",
        "reviewDecision": "",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "isDraft": False,
        "body": "Adds OAuth 2.0 auth flow",
        "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
    },
    # 4. Self-authored test PR (Ready CI, self-authored)
    {
        "number": 202,
        "title": "test: Improve test coverage for HTTP client error handling",
        "author": {"login": "allenporter", "is_bot": False},
        "createdAt": "2026-07-25T12:00:00Z",
        "headRefName": "test/client-exceptions-coverage",
        "reviewDecision": "",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "isDraft": False,
        "body": "Improves test coverage",
        "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
    },
    # 5. Cruft update PR (Ready CI, valid internal cruft PR)
    {
        "number": 301,
        "title": "Apply cruft updates",
        "author": {"login": "allenporter", "is_bot": False},
        "createdAt": "2026-07-25T12:00:00Z",
        "headRefName": "cruft-update",
        "reviewDecision": "",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "isDraft": False,
        "body": "Apply cruft template updates",
        "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
        "mock_diff_files": ["pyproject.toml"],
    },
    # 6. Cruft update PR with .rej files (Conflict -> Attention Required)
    {
        "number": 302,
        "title": "Apply cruft updates",
        "author": {"login": "allenporter", "is_bot": False},
        "createdAt": "2026-07-25T12:00:00Z",
        "headRefName": "cruft-update",
        "reviewDecision": "",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "isDraft": False,
        "body": "Apply cruft template updates",
        "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
        "mock_diff_files": ["pyproject.toml.rej"],
    },
]


@patch("repo_conformance.prs.parse_manifest")
def test_prs_renovate_filter_strictly_excludes_self_authored_and_cruft_with_fake(
    mock_parse_manifest: MagicMock,
) -> None:
    """Verify that --renovate filter STRICTLY matches Renovate bot PRs using FakeGitHubClient."""

    mock_manifest = Manifest(
        user="allenporter", repos=[Repo(name="test-repo", user="allenporter")]
    )
    mock_parse_manifest.return_value = mock_manifest

    fake_client = FakeGitHubClient({"allenporter/test-repo": MOCK_PRS_PAYLOAD})

    action = PrsAction()

    with patch("builtins.print") as mock_print:
        action.run(
            repo=None,
            renovate=True,
            merge=True,
            dry_run=True,
            yes=True,
            client=fake_client,
        )

        printed_lines = [
            call.args[0] for call in mock_print.call_args_list if call.args
        ]

        # Verify Renovate patch PR #101 is included
        assert any("#101" in line for line in printed_lines)

        # Verify self-authored feature PRs #201, #202 are STRICTLY EXCLUDED
        assert not any("#201" in line for line in printed_lines)
        assert not any("#202" in line for line in printed_lines)

        # Verify Cruft PR #301 is STRICTLY EXCLUDED from --renovate merge
        assert not any("#301" in line for line in printed_lines)

        # Verify major bump PR #102 is EXCLUDED from default auto-merge without --allow-major
        assert not any("#102" in line for line in printed_lines)


@patch("repo_conformance.prs.parse_manifest")
def test_prs_renovate_actual_merge_execution_with_fake(
    mock_parse_manifest: MagicMock,
) -> None:
    """Verify that --renovate --merge actually executes merges on FakeGitHubClient for valid PRs ONLY."""

    mock_manifest = Manifest(
        user="allenporter", repos=[Repo(name="test-repo", user="allenporter")]
    )
    mock_parse_manifest.return_value = mock_manifest

    fake_client = FakeGitHubClient({"allenporter/test-repo": MOCK_PRS_PAYLOAD})

    action = PrsAction()
    action.run(
        repo=None,
        renovate=True,
        merge=True,
        dry_run=False,  # Actual merge
        yes=True,
        client=fake_client,
    )

    # EXACTLY PR #101 must be merged. ZERO self-authored PRs (#201, #202) or Cruft PRs (#301, #302)
    assert fake_client.merged_prs == [("allenporter/test-repo", 101)]


@patch("repo_conformance.prs.parse_manifest")
def test_prs_cruft_filter_accepts_valid_and_rejects_rej_files(
    mock_parse_manifest: MagicMock,
) -> None:
    """Verify that --cruft --merge matches clean Cruft PR #301 and REJECTS PR #302 with .rej conflict files."""

    mock_manifest = Manifest(
        user="allenporter", repos=[Repo(name="test-repo", user="allenporter")]
    )
    mock_parse_manifest.return_value = mock_manifest

    fake_client = FakeGitHubClient({"allenporter/test-repo": MOCK_PRS_PAYLOAD})

    action = PrsAction()
    action.run(
        repo=None,
        cruft=True,
        merge=True,
        dry_run=False,
        yes=True,
        client=fake_client,
    )

    # EXACTLY clean Cruft PR #301 must be merged. PR #302 (has .rej files) MUST NOT BE MERGED.
    assert fake_client.merged_prs == [("allenporter/test-repo", 301)]


@patch("repo_conformance.prs.parse_manifest")
def test_prs_naked_merge_disabled_for_safety(
    mock_parse_manifest: MagicMock,
) -> None:
    """Verify that naked --merge without --renovate or --cruft raises SystemExit(1) for safety."""

    mock_manifest = Manifest(
        user="allenporter", repos=[Repo(name="test-repo", user="allenporter")]
    )
    mock_parse_manifest.return_value = mock_manifest

    fake_client = FakeGitHubClient({"allenporter/test-repo": MOCK_PRS_PAYLOAD})

    action = PrsAction()

    with pytest.raises(SystemExit) as exc_info:
        action.run(
            repo=None,
            merge=True,  # Naked merge without --renovate or --cruft
            yes=True,
            client=fake_client,
        )

    assert exc_info.value.code == 1
    assert len(fake_client.merged_prs) == 0


@patch("repo_conformance.prs.parse_manifest")
def test_prs_renovate_allow_major_includes_major_bump_with_fake(
    mock_parse_manifest: MagicMock,
) -> None:
    """Verify that --renovate --merge --allow-major includes major version bumps using FakeGitHubClient."""

    mock_manifest = Manifest(
        user="allenporter", repos=[Repo(name="test-repo", user="allenporter")]
    )
    mock_parse_manifest.return_value = mock_manifest

    fake_client = FakeGitHubClient({"allenporter/test-repo": MOCK_PRS_PAYLOAD})

    action = PrsAction()
    action.run(
        repo=None,
        renovate=True,
        merge=True,
        allow_major=True,
        dry_run=False,
        yes=True,
        client=fake_client,
    )

    # Both patch #101 and major #102 should be merged when allow_major=True
    assert ("allenporter/test-repo", 101) in fake_client.merged_prs
    assert ("allenporter/test-repo", 102) in fake_client.merged_prs

    # Self-authored PRs MUST STILL BE EXCLUDED
    assert ("allenporter/test-repo", 201) not in fake_client.merged_prs
    assert ("allenporter/test-repo", 202) not in fake_client.merged_prs
