"""Action to inspect main branch CI workflow statuses across manifest repositories."""

import json
import logging
import subprocess
import sys
from argparse import ArgumentParser, BooleanOptionalAction
from argparse import _SubParsersAction as SubParsersAction
from typing import cast

from .manifest import parse_manifest
from .prs import GitHubClient, format_age

_LOGGER = logging.getLogger(__name__)


def get_run_status(run: dict, color: bool = True) -> str:
    """Determine CI run status from a GitHub Actions workflow run dict."""
    status = run.get("status", "").upper()
    conclusion = (run.get("conclusion") or "").upper()

    if status in ["IN_PROGRESS", "QUEUED", "WAITING", "PENDING"]:
        return "\033[93m🟡 IN_PROGRESS\033[0m" if color else "🟡 IN_PROGRESS"
    if conclusion == "SUCCESS":
        return "\033[92m🟢 PASSED\033[0m" if color else "🟢 PASSED"
    if conclusion in ["FAILURE", "TIMED_OUT", "STARTUP_FAILURE", "CANCELLED"]:
        return "\033[91m🔴 FAILED\033[0m" if color else "🔴 FAILED"
    if conclusion == "SKIPPED":
        return "\033[90m⚪ SKIPPED\033[0m" if color else "⚪ SKIPPED"
    return f"\033[93m🟡 {status}\033[0m" if color else f"🟡 {status}"


class CiAction:
    """Action to inspect main branch CI statuses."""

    @classmethod
    def register(cls, subparsers: SubParsersAction) -> ArgumentParser:
        args = cast(
            ArgumentParser,
            subparsers.add_parser(
                "ci", help="Inspect default branch (main) CI workflow run statuses"
            ),
        )
        args.add_argument(
            "repo",
            help="The name of the repo to inspect, or all if omitted",
            type=str,
            default=None,
            nargs="?",
        )
        args.add_argument(
            "--failed",
            help="Show only repositories or workflows with failing CI status",
            default=False,
            action=BooleanOptionalAction,
        )
        args.add_argument(
            "--limit",
            help="Number of recent workflow runs to inspect per repository (default: 3)",
            type=int,
            default=3,
        )
        args.set_defaults(cls=CiAction)
        return args

    def run(  # type: ignore[no-untyped-def]
        self,
        repo: str | None = None,
        failed: bool = False,
        limit: int = 3,
        client: GitHubClient | None = None,
        **kwargs,  # pylint: disable=unused-argument
    ) -> None:
        """Run implementation."""
        manifest = parse_manifest()
        github_client = client or GitHubClient()

        if not github_client.check_auth():
            print(
                "Error: Please log in using the GitHub CLI with `gh auth login`.",
                file=sys.stderr,
            )
            sys.exit(1)

        has_results = False

        for r in manifest.repos:
            if repo and r.name != repo:
                continue

            user = r.user or manifest.user
            repo_fullname = f"{user}/{r.name}"

            res = subprocess.run(
                [
                    "gh",
                    "run",
                    "list",
                    "--repo",
                    repo_fullname,
                    "--branch",
                    "main",
                    "--limit",
                    str(limit),
                    "--json",
                    "name,status,conclusion,event,createdAt,url,headSha",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            if res.returncode != 0:
                continue

            try:
                runs = json.loads(res.stdout)
            except json.JSONDecodeError:
                runs = []

            if not runs:
                continue

            if failed:
                runs = [
                    run
                    for run in runs
                    if (run.get("conclusion") or "").upper()
                    in ["FAILURE", "TIMED_OUT", "STARTUP_FAILURE"]
                ]
                if not runs:
                    continue

            has_results = True
            print(f"\n\033[1m{r.name}\033[0m ({repo_fullname}):")
            for run in runs:
                name = run.get("name", "Workflow")
                status_str = get_run_status(run, color=True)
                age = format_age(run.get("createdAt", ""))
                event = run.get("event", "push")
                print(f"  {status_str} {name} (event: {event}, {age} ago)")

        if not has_results:
            print("\nNo matching main branch CI runs found.\n")
        else:
            print()
