"""Action to display and export a unified repository health dashboard."""

import base64
import concurrent.futures
import json
import logging
import pathlib
import subprocess
import sys
from argparse import ArgumentParser
from argparse import _SubParsersAction as SubParsersAction
from typing import cast

from .checks.cruft import get_latest_commit
from .manifest import parse_manifest
from .prs import GitHubClient, get_ci_status

_LOGGER = logging.getLogger(__name__)


class DashboardAction:
    """Action to present a unified health dashboard across all manifest repositories."""

    @classmethod
    def register(cls, subparsers: SubParsersAction) -> ArgumentParser:
        args = cast(
            ArgumentParser,
            subparsers.add_parser(
                "dashboard", help="Unified health dashboard across all repositories"
            ),
        )
        args.add_argument(
            "--export",
            help="Path to export the markdown health dashboard report (default: REPOS_HEALTH.md)",
            type=pathlib.Path,
            nargs="?",
            const=pathlib.Path("REPOS_HEALTH.md"),
            default=None,
        )
        args.set_defaults(cls=DashboardAction)
        return args

    def run(  # type: ignore[no-untyped-def]
        self,
        export: pathlib.Path | None = None,
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

        print("\n\033[1mGenerating Repository Health Dashboard...\033[0m")

        results = []

        def inspect_repo(r):
            user = r.user or manifest.user
            repo_fullname = f"{user}/{r.name}"

            # 1. Inspect Cruft template status
            cruft_status = "OK"
            cruft_detail = "Up to date"
            try:
                res_cruft = subprocess.run(
                    [
                        "gh",
                        "api",
                        f"repos/{repo_fullname}/contents/.cruft.json",
                        "-q",
                        ".content",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if res_cruft.returncode == 0:
                    cruft_json_str = base64.b64decode(res_cruft.stdout.strip()).decode(
                        "utf-8"
                    )
                    cruft_cfg = json.loads(cruft_json_str)
                    template_url = cruft_cfg.get("template", "").rstrip("/")
                    tmpl_fullname = "/".join(template_url.split("/")[-2:])
                    current_commit = cruft_cfg.get("commit", "")
                    latest_commit = get_latest_commit(tmpl_fullname)
                    if current_commit != latest_commit:
                        cruft_status = "DRIFT"
                        cruft_detail = (
                            f"Expected {latest_commit[:7]}, got {current_commit[:7]}"
                        )
                else:
                    cruft_status = "N/A"
                    cruft_detail = "No .cruft.json"
            except Exception as err:  # noqa: BLE001
                cruft_status = "ERROR"
                cruft_detail = str(err)

            # 2. Inspect Main Branch CI Status
            ci_status = "UNKNOWN"
            res_ci = subprocess.run(
                [
                    "gh",
                    "run",
                    "list",
                    "--repo",
                    repo_fullname,
                    "--branch",
                    "main",
                    "--limit",
                    "1",
                    "--json",
                    "conclusion,status",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if res_ci.returncode == 0:
                try:
                    runs = json.loads(res_ci.stdout)
                    if runs:
                        latest_run = runs[0]
                        st = latest_run.get("status", "").upper()
                        conc = (latest_run.get("conclusion") or "").upper()
                        if st in ["IN_PROGRESS", "QUEUED", "PENDING"]:
                            ci_status = "PENDING"
                        elif conc == "SUCCESS":
                            ci_status = "PASSED"
                        elif conc in ["FAILURE", "TIMED_OUT", "STARTUP_FAILURE"]:
                            ci_status = "FAILED"
                        else:
                            ci_status = conc or st
                    else:
                        ci_status = "NO_RUNS"
                except json.JSONDecodeError:
                    ci_status = "ERROR"

            # 3. Inspect Open PRs
            prs = github_client.list_prs(repo_fullname)
            ready_cnt = 0
            pending_cnt = 0
            attention_cnt = 0

            for pr in prs:
                checks_list = pr.get("statusCheckRollup", [])
                ci_str = get_ci_status(checks_list, color=False)
                m_state = pr.get("mergeable", "UNKNOWN")
                m_status = pr.get("mergeStateStatus", "UNKNOWN")
                rev_decision = pr.get("reviewDecision", "")

                is_failed = "FAILED" in ci_str
                is_conflicting = (m_state == "CONFLICTING") or (m_status == "DIRTY")
                is_changes_requested = rev_decision == "CHANGES_REQUESTED"

                if is_failed or is_conflicting or is_changes_requested:
                    attention_cnt += 1
                elif pr.get("isDraft", False):
                    pending_cnt += 1
                elif "PASSED" in ci_str or ci_str == "No checks":
                    ready_cnt += 1
                else:
                    pending_cnt += 1

            return {
                "name": r.name,
                "fullname": repo_fullname,
                "cruft_status": cruft_status,
                "cruft_detail": cruft_detail,
                "ci_status": ci_status,
                "ready_prs": ready_cnt,
                "pending_prs": pending_cnt,
                "attention_prs": attention_cnt,
                "total_prs": len(prs),
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_repo = {
                executor.submit(inspect_repo, r): r for r in manifest.repos
            }
            for future in concurrent.futures.as_completed(future_to_repo):
                results.append(future.result())

        # Sort results by repository name
        results.sort(key=lambda x: x["name"])

        # Display terminal dashboard
        print(
            f"\n{'Repository':<35} {'Template Sync':<22} {'Main CI':<12} {'Open PRs (R/P/A)':<18}"
        )
        print("-" * 88)
        for row in results:
            # Color code template status
            if row["cruft_status"] == "OK":
                cruft_str = "\033[92m🟢 Up to date\033[0m"
            elif row["cruft_status"] == "DRIFT":
                cruft_str = f"\033[91m🔴 Drift ({row['cruft_detail']})\033[0m"
            else:
                cruft_str = f"\033[90m⚪ {row['cruft_detail']}\033[0m"

            # Color code CI status
            if row["ci_status"] == "PASSED":
                ci_str = "\033[92m🟢 PASSED\033[0m"
            elif row["ci_status"] == "FAILED":
                ci_str = "\033[91m🔴 FAILED\033[0m"
            elif row["ci_status"] == "PENDING":
                ci_str = "\033[93m🟡 PENDING\033[0m"
            else:
                ci_str = f"⚪ {row['ci_status']}"

            pr_str = f"{row['ready_prs']} ready / {row['pending_prs']} pend / {row['attention_prs']} attn"
            if row["attention_prs"] > 0:
                pr_str = f"\033[91m{pr_str}\033[0m"
            elif row["ready_prs"] > 0:
                pr_str = f"\033[92m{pr_str}\033[0m"

            print(f"{row['name']:<35} {cruft_str:<31} {ci_str:<21} {pr_str}")
        print()

        # Handle Markdown Export if requested
        if export:
            md_lines = [
                "# Repository Health Dashboard",
                "",
                "Automated status snapshot of all manifest-configured repositories.",
                "",
                "| Repository | Template Sync | Main Branch CI | Ready PRs | Pending PRs | Attention Required |",
                "| :--- | :--- | :--- | :---: | :---: | :---: |",
            ]
            for row in results:
                cruft_icon = (
                    "🟢 Up to date"
                    if row["cruft_status"] == "OK"
                    else (
                        f"🔴 Drift ({row['cruft_detail']})"
                        if row["cruft_status"] == "DRIFT"
                        else row["cruft_detail"]
                    )
                )
                ci_icon = (
                    "🟢 PASSED"
                    if row["ci_status"] == "PASSED"
                    else (
                        "🔴 FAILED"
                        if row["ci_status"] == "FAILED"
                        else (
                            "🟡 PENDING"
                            if row["ci_status"] == "PENDING"
                            else row["ci_status"]
                        )
                    )
                )
                md_lines.append(
                    f"| `{row['name']}` | {cruft_icon} | {ci_icon} | {row['ready_prs']} | {row['pending_prs']} | {row['attention_prs']} |"
                )

            md_content = "\n".join(md_lines) + "\n"
            export.write_text(md_content, encoding="utf-8")
            print(f"\033[92m✓ Exported health dashboard to {export}\033[0m\n")
