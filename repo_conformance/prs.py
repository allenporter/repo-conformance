"""Action to inspect and manage open pull requests in manifest repositories."""

import subprocess
import json
import logging
import sys
from datetime import datetime, timezone
from argparse import ArgumentParser, BooleanOptionalAction
from argparse import _SubParsersAction as SubParsersAction
from typing import cast

from .manifest import parse_manifest


_LOGGER = logging.getLogger(__name__)


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string, handling UTC 'Z' suffix."""
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    return datetime.fromisoformat(dt_str)


def format_age(dt_str: str) -> str:
    """Format the duration since the given ISO datetime string."""
    try:
        created = parse_iso_datetime(dt_str)
        now = datetime.now(timezone.utc)
        diff = now - created
        if diff.days > 0:
            return f"{diff.days}d"
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours}h"
        minutes = (diff.seconds % 3600) // 60
        return f"{minutes}m"
    except Exception:
        return "unknown"


def get_ci_status(checks: list[dict], color: bool = True) -> str:
    """Determine CI status of a PR from its statusCheckRollup."""
    if not checks:
        return "No checks"

    has_failure = False
    has_pending = False

    for check in checks:
        status = check.get("status")
        conclusion = check.get("conclusion")
        state = check.get("state")

        if conclusion == "FAILURE" or state == "FAILURE" or conclusion == "failed" or state == "failed":
            has_failure = True
        elif status in ["IN_PROGRESS", "QUEUED", "pending", "expected"] or (not conclusion and not state):
            has_pending = True

    if has_failure:
        return "\033[91m🔴 FAILED\033[0m" if color else "🔴 FAILED"
    if has_pending:
        return "\033[93m🟡 PENDING\033[0m" if color else "🟡 PENDING"
    return "\033[92m🟢 PASSED\033[0m" if color else "🟢 PASSED"


def is_trusted_author(pr: dict, manifest_user: str) -> bool:
    """Check if the PR is authored by a trusted entity (self or a bot)."""
    author_login = pr.get("author", {}).get("login", "").lower()
    is_bot = pr.get("author", {}).get("is_bot", False)
    return (
        author_login == manifest_user.lower() or
        is_bot or
        "renovate" in author_login or
        "dependabot" in author_login
    )


class PrsAction:
    """PR Status and Health action."""

    @classmethod
    def register(cls, subparsers: SubParsersAction) -> ArgumentParser:
        args = cast(
            ArgumentParser,
            subparsers.add_parser("prs", help="Inspect and analyze open Pull Requests"),
        )
        args.add_argument(
            "repo",
            help="The name of the repo to inspect, or all if omitted",
            type=str,
            default=None,
            nargs="?",
        )
        args.add_argument(
            "--renovate",
            help="Filter for Renovate dependency PRs",
            default=False,
            action=BooleanOptionalAction,
        )
        args.add_argument(
            "--cruft",
            help="Filter for Cruft update PRs",
            default=False,
            action=BooleanOptionalAction,
        )
        args.add_argument(
            "--all",
            help="Show all open pull requests (including features and community PRs)",
            default=False,
            action=BooleanOptionalAction,
        )
        args.add_argument(
            "--author",
            help="Filter by author username (use 'me' for manifest user)",
            type=str,
            default=None,
        )
        args.add_argument(
            "--health",
            help="Print aggregated review queue health metrics",
            default=False,
            action=BooleanOptionalAction,
        )
        args.add_argument(
            "--checks",
            help="Show detailed CI status checks for open PRs",
            default=False,
            action=BooleanOptionalAction,
        )
        args.add_argument(
            "--merge",
            help="Merge all passing and approved/auto-mergeable PRs",
            default=False,
            action=BooleanOptionalAction,
        )
        args.add_argument(
            "-y",
            "--yes",
            help="Confirm bulk merge without prompting",
            default=False,
            action=BooleanOptionalAction,
        )
        args.add_argument(
            "--dry-run",
            help="Show PRs that would be merged without merging them",
            default=False,
            action=BooleanOptionalAction,
        )
        args.set_defaults(cls=PrsAction)
        return args

    def run(  # type: ignore[no-untyped-def]
        self,
        repo: str | None,
        renovate: bool = False,
        cruft: bool = False,
        author: str | None = None,
        health: bool = False,
        checks: bool = False,
        merge: bool = False,
        yes: bool = False,
        dry_run: bool = False,
        **kwargs,  # pylint: disable=unused-argument
    ) -> None:
        """Run implementation."""
        manifest = parse_manifest()

        # Verify the user is logged into the gh CLI
        try:
            subprocess.run(
                ["gh", "auth", "status"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            print(
                "Error: Please log in using the GitHub CLI with `gh auth login`.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Resolve 'me' keyword to manifest user
        target_author = manifest.user if author == "me" else author
        if target_author:
            target_author = target_author.lower()

        # Collect data for all matching repos
        repos_data = []

        for r in manifest.repos:
            if repo and r.name != repo:
                continue

            if not r.user:
                r.user = manifest.user

            repo_fullname = f"{r.user}/{r.name}"

            res = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--repo",
                    repo_fullname,
                    "--json",
                    "number,title,url,state,statusCheckRollup,author,createdAt,headRefName,reviewDecision,mergeable,mergeStateStatus,isDraft",
                ],
                capture_output=True,
                text=True,
            )

            if res.returncode != 0:
                _LOGGER.debug("Skipping %s: %s", repo_fullname, res.stderr.strip())
                continue

            try:
                prs = json.loads(res.stdout)
            except json.JSONDecodeError:
                continue

            filtered_prs = []
            for pr in prs:
                pr_author = pr.get("author", {}).get("login", "").lower()
                pr_title = pr.get("title", "")
                head_ref = pr.get("headRefName", "")

                is_renovate = "renovate" in pr_author
                is_dependabot = "dependabot" in pr_author
                is_cruft = "cruft" in pr_title.lower() or head_ref == "cruft-update"
                is_maintenance = is_renovate or is_dependabot or is_cruft

                # Apply specific filters if set
                if renovate and not is_renovate:
                    continue
                if cruft and not is_cruft:
                    continue
                if target_author and pr_author != target_author:
                    continue

                # Default: only show maintenance PRs unless --all is specified
                if not (renovate or cruft or target_author or kwargs.get("all")):
                    if not is_maintenance:
                        continue

                filtered_prs.append(pr)

            if filtered_prs or health or checks or merge:
                # Group PRs by status
                grouped = {"ready": [], "pending": [], "attention": []}
                for pr in filtered_prs:
                    checks_list = pr.get("statusCheckRollup", [])
                    ci_str = get_ci_status(checks_list, color=False)
                    m_state = pr.get("mergeable", "UNKNOWN")
                    m_status = pr.get("mergeStateStatus", "UNKNOWN")
                    rev_decision = pr.get("reviewDecision", "")
                    is_draft = pr.get("isDraft", False)
                    
                    head_ref = pr.get("headRefName", "")
                    pr_title = pr.get("title", "")
                    is_cruft = "cruft" in pr_title.lower() or head_ref == "cruft-update"

                    is_failed = "FAILED" in ci_str
                    is_conflicting = (m_state == "CONFLICTING") or (m_status == "DIRTY")
                    is_changes_requested = rev_decision == "CHANGES_REQUESTED"
                    
                    # Fetch file list for cruft PRs to check for .rej files
                    has_rej_files = False
                    if is_cruft:
                        files_res = subprocess.run(
                            ["gh", "pr", "diff", str(pr.get("number")), "--repo", repo_fullname, "--name-only"],
                            capture_output=True,
                            text=True
                        )
                        if files_res.returncode == 0:
                            modified_files = files_res.stdout.splitlines()
                            if any(f.endswith(".rej") for f in modified_files):
                                has_rej_files = True
                    
                    # Store has_rej_files in the PR dict
                    pr["has_rej_files"] = has_rej_files

                    is_passed = "PASSED" in ci_str or ci_str == "No checks"
                    is_mergeable = (m_state == "MERGEABLE") or (m_status in ["CLEAN", "HAS_HOOKS"])
                    is_approved_or_no_review = rev_decision in ["APPROVED", "", "NONE", None]

                    if is_failed or is_conflicting or is_changes_requested or has_rej_files:
                        grouped["attention"].append(pr)
                    elif is_draft:
                        grouped["pending"].append(pr)
                    elif is_passed and is_mergeable and is_approved_or_no_review:
                        grouped["ready"].append(pr)
                    else:
                        grouped["pending"].append(pr)

                repos_data.append((r.name, repo_fullname, grouped))

        # Handle --checks execution
        if checks:
            has_prs = False
            for name, fullname, groups in repos_data:
                all_prs = groups["ready"] + groups["pending"] + groups["attention"]
                if not all_prs:
                    continue
                has_prs = True
                for pr in all_prs:
                    num = pr.get("number")
                    title = pr.get("title")
                    print(f"\n\033[1mChecks for {name} #{num}\033[0m: {title}")
                    print("-" * 60)
                    res_checks = subprocess.run(
                        ["gh", "pr", "checks", str(num), "--repo", fullname],
                        capture_output=True,
                        text=True,
                    )
                    if res_checks.returncode == 0 or res_checks.stdout:
                        print(res_checks.stdout)
                    else:
                        print(res_checks.stderr or "Failed to retrieve check details.")
            if not has_prs:
                print("\nNo open pull requests found matching the criteria.\n")
            return

        # Handle --merge execution
        if merge:
            ready_to_merge_all = []
            for name, fullname, groups in repos_data:
                for pr in groups["ready"]:
                    # Safety check: enforce trusted author constraint
                    if is_trusted_author(pr, manifest.user):
                        ready_to_merge_all.append((name, fullname, pr))

            if not ready_to_merge_all:
                print("\nNo pull requests are ready to merge.\n")
                return

            print("\nPull requests ready to merge:")
            for name, fullname, pr in ready_to_merge_all:
                num = pr.get("number")
                title = pr.get("title")
                author_login = pr.get("author", {}).get("login", "unknown")
                age = format_age(pr.get("createdAt", ""))
                print(f"  [{name}] #{num:<4} {title} [@{author_login}] ({age})")

            if dry_run:
                print("\n[Dry-run] Would merge the above pull requests.\n")
                return

            if not yes:
                confirm = input(f"\nProceed with merging these {len(ready_to_merge_all)} pull requests? [y/N]: ")
                if confirm.strip().lower() not in ["y", "yes"]:
                    print("Merge cancelled.")
                    return

            print("\nMerging pull requests...")
            for name, fullname, pr in ready_to_merge_all:
                num = pr.get("number")
                print(f"Merging {name} #{num}...")
                merge_res = subprocess.run(
                    ["gh", "pr", "merge", str(num), "--repo", fullname, "--squash", "--delete-branch"],
                    capture_output=True,
                    text=True,
                )
                if merge_res.returncode == 0:
                    print(f"  \033[92m✓ Successfully merged {name} #{num}\033[0m")
                else:
                    print(f"  \033[91m✗ Failed to merge {name} #{num}: {merge_res.stderr.strip()}\033[0m")
            print()
            return

        # Handle --health report
        if health:
            print(
                f"\n\033[1m{'Repository':<40} {'Open':<6} {'Ready':<8} {'Pending':<8} {'Attention':<10} {'Oldest':<8}\033[0m"
            )
            print("-" * 86)
            for name, fullname, groups in repos_data:
                ready_cnt = len(groups["ready"])
                pending_cnt = len(groups["pending"])
                attention_cnt = len(groups["attention"])
                open_cnt = ready_cnt + pending_cnt + attention_cnt
                oldest_age = "-"

                created_times = []
                for pr in groups["ready"] + groups["pending"] + groups["attention"]:
                    created_at = pr.get("createdAt")
                    if created_at:
                        created_times.append(created_at)

                if created_times:
                    oldest_age = format_age(min(created_times))

                print(
                    f"{name:<40} {open_cnt:<6} {ready_cnt:<8} {pending_cnt:<8} {attention_cnt:<10} {oldest_age:<8}"
                )
            print()
            return

        # Handle default print view
        has_prs = False
        for name, fullname, groups in repos_data:
            if not (groups["ready"] or groups["pending"] or groups["attention"]):
                continue
            has_prs = True
            print(f"\n\033[1m{name}\033[0m:")

            def print_pr_list(prs: list[dict], prefix: str):
                for pr in prs:
                    num = pr.get("number")
                    title = pr.get("title")
                    author_login = pr.get("author", {}).get("login", "unknown")
                    checks_list = pr.get("statusCheckRollup", [])
                    ci_str = get_ci_status(checks_list, color=True)
                    age = format_age(pr.get("createdAt", ""))

                    m_state = pr.get("mergeable", "UNKNOWN")
                    m_status = pr.get("mergeStateStatus", "UNKNOWN")
                    rev_decision = pr.get("reviewDecision", "")
                    is_draft = pr.get("isDraft", False)
                    has_rej_files = pr.get("has_rej_files", False)

                    details = []
                    if is_draft:
                        details.append("\033[93mDraft\033[0m")
                    if m_state == "CONFLICTING" or m_status == "DIRTY":
                        details.append("\033[91mCONFLICT\033[0m")
                    if has_rej_files:
                        details.append("\033[91mREJECT FILES\033[0m")
                    if rev_decision == "REVIEW_REQUIRED":
                        details.append("\033[93mNeeds Review\033[0m")
                    elif rev_decision == "CHANGES_REQUESTED":
                        details.append("\033[91mChanges Requested\033[0m")
                    elif rev_decision == "APPROVED":
                        details.append("\033[92mApproved\033[0m")

                    details_str = f" [{', '.join(details)}]" if details else ""
                    print(f"  {prefix} #{num:<4} {title} [@{author_login}] ({age}) - {ci_str}{details_str}")

            if groups["ready"]:
                print_pr_list(groups["ready"], "🟢")
            if groups["pending"]:
                print_pr_list(groups["pending"], "🟡")
            if groups["attention"]:
                print_pr_list(groups["attention"], "🔴")

        if not has_prs:
            print("\nNo open pull requests found matching the criteria.\n")
        else:
            print()
