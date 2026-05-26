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

        if conclusion == "FAILURE":
            has_failure = True
        elif status in ["IN_PROGRESS", "QUEUED"] or not conclusion:
            has_pending = True

    if has_failure:
        return "\033[91m🔴 FAILED\033[0m" if color else "🔴 FAILED"
    if has_pending:
        return "\033[93m🟡 PENDING\033[0m" if color else "🟡 PENDING"
    return "\033[92m🟢 PASSED\033[0m" if color else "🟢 PASSED"


def get_ci_weight(ci_text: str) -> int:
    """Assign weight for prioritization sorting."""
    if "FAILED" in ci_text:
        return 0
    if "PENDING" in ci_text:
        return 1
    if "PASSED" in ci_text:
        return 2
    return 3


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
        args.set_defaults(cls=PrsAction)
        return args

    def run(  # type: ignore[no-untyped-def]
        self,
        repo: str | None,
        renovate: bool = False,
        cruft: bool = False,
        author: str | None = None,
        health: bool = False,
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
                    "number,title,url,state,statusCheckRollup,author,createdAt,headRefName",
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

                # Apply --renovate filter
                if renovate and "renovate" not in pr_author:
                    continue

                # Apply --cruft filter
                is_cruft = (
                    "cruft" in pr_title.lower()
                    or pr.get("headRefName") == "cruft-update"
                )
                if cruft and not is_cruft:
                    continue

                # Apply --author filter
                if target_author and pr_author != target_author:
                    continue

                filtered_prs.append(pr)

            if filtered_prs or health:
                repos_data.append((r.name, repo_fullname, filtered_prs))

        if health:
            # Print aggregated metrics report
            print(
                f"\n\033[1m{'Repository':<40} {'Open':<6} {'Passed':<8} {'Failed':<8} {'Pending':<8} {'Oldest':<8}\033[0m"
            )
            print("-" * 86)
            for name, fullname, prs in repos_data:
                open_cnt = len(prs)
                passed_cnt = 0
                failed_cnt = 0
                pending_cnt = 0
                oldest_age = "-"

                created_times = []
                for pr in prs:
                    checks = pr.get("statusCheckRollup", [])
                    ci = get_ci_status(checks, color=False)
                    if "PASSED" in ci:
                        passed_cnt += 1
                    elif "FAILED" in ci:
                        failed_cnt += 1
                    elif "PENDING" in ci:
                        pending_cnt += 1

                    created_at = pr.get("createdAt")
                    if created_at:
                        created_times.append(created_at)

                if created_times:
                    # Find oldest (which is the min date string since ISO strings sort chronologically)
                    oldest_age = format_age(min(created_times))

                print(
                    f"{name:<40} {open_cnt:<6} {passed_cnt:<8} {failed_cnt:<8} {pending_cnt:<8} {oldest_age:<8}"
                )
            print()
        else:
            # Print standard detailed PR list
            has_prs = False
            for name, fullname, prs in repos_data:
                if not prs:
                    continue
                has_prs = True
                print(f"\n\033[1m{name}\033[0m:")

                # Sort by CI weight, then by creation date (oldest first)
                sorted_prs = sorted(
                    prs,
                    key=lambda x: (
                        get_ci_weight(
                            get_ci_status(x.get("statusCheckRollup", []), color=False)
                        ),
                        x.get("createdAt", ""),
                    ),
                )

                for pr in sorted_prs:
                    num = pr.get("number")
                    title = pr.get("title")
                    author_login = pr.get("author", {}).get("login", "unknown")
                    checks = pr.get("statusCheckRollup", [])
                    ci = get_ci_status(checks, color=True)
                    age = format_age(pr.get("createdAt", ""))

                    print(f"  #{num:<4} {title} [@{author_login}] ({age}) - {ci}")

            if not has_prs:
                print("\nNo open pull requests found matching the criteria.\n")
            else:
                print()
