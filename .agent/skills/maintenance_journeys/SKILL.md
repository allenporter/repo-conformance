---
name: maintenance_journeys
description: Operational guide for codebase maintenance, covering both the human-in-the-loop "Saturday Review" and the fully autonomous "Autopilot Agent" workflows.
---

# Codebase Maintenance Journeys

This skill defines the workflows and command sequences for keeping repositories in the manifest up-to-date with template changes and dependency upgrades.

---

## 🗓️ Journey 1: "The Saturday Review" (Operator-led / Human-in-the-Loop)

Designed for a human maintainer (or an agent working interactively with the user) to review and clean up open PRs quickly.

### Step 1: Fetch and Inspect the Current State
Open a terminal in the `repo-conformance` workspace and run the status command:
```bash
uv run repo prs
```
This prints the status of all open Renovate and Cruft update PRs, grouped by their readiness status:
* **🟢 Ready to Merge**: Green, approved, or auto-mergeable PRs.
* **🟡 Pending / In Progress**: Checks running or waiting on human review decision.
* **🔴 Attention Required**: PRs that have failed tests or have merge conflicts.

For a high-level summary of open queues, run:
```bash
uv run repo prs --health
```

### Step 2: Auto-Merge Low-Risk / Green Upgrades
Merge all the low-risk dependency and template upgrades that have fully passed CI checks:
```bash
uv run repo prs --merge
```
This runs safety checks to ensure only trusted authors (`allenporter` or Renovate bots) and approved/auto-mergeable PRs are targetable. It lists the candidate PRs and prompts for confirmation. To skip the prompt (e.g. in automated scripts), run:
```bash
uv run repo prs --merge --yes
```

### Step 3: Diagnose Failed Checks
For any PR listed in the `🔴 Attention Required` section, inspect the detailed CI checks to see why they failed:
```bash
uv run repo prs <repo_name> --checks
```
This outputs the names of the failing test suites (e.g., `pre-commit`, `pytest`) and direct links to their logs.

### Step 4: Resolve Merge Conflicts or Failures
* If it is a template update conflict (indicated by `CONFLICT` status in the PR list), use the **`cruft_resolution`** skill to spawn a local worktree, run `scruft update`, resolve conflicts, verify the code builds/tests pass, and force-push the fixed update.
* If a Renovate dependency upgrade broke tests, checkout the Renovate branch, resolve the library compatibility issue, and commit the fix to the branch.

---

## 🤖 Journey 2: "The Autopilot Agent" (Fully Autonomous)

Designed for background agents (such as a cron job or scheduled worker) to automate the repository update pipeline without human intervention.

### Step 1: Scan and Pull Template Changes
The agent loops through all repositories in the manifest and triggers parallel Cruft template updates:
```bash
# Update a specific repo (running in parallel via subagents)
uv run repo update_repo <repo_name>
```
If a repository is already up-to-date, the command finishes immediately. If changes are detected, it creates a `cruft-update` branch, commits the updates, and opens a GitHub Pull Request.

### Step 2: Safety Check and Auto-Merge
The agent runs a scan to find open PRs that are fully green and safe to merge:
```bash
uv run repo prs --merge --yes
```
If a PR requires manual review (e.g., a major version upgrade with API changes), the safety check in `prs.py` blocks the auto-merge.

### Step 3: Escalate and Flag Failures
If a template update PR fails checks or has merge conflicts, the agent:
1. Does **not** merge the PR.
2. Runs `gh pr checks` to extract the error log URLs.
3. Updates the **Executive Cockpit** (`dashboard/active_inbox.md` in `opensource-ops`) to flag the repository under the `🚨 Attention Required` maintenance section, detailing the exact error and log URLs so the operator can inspect it during their Saturday Review.
