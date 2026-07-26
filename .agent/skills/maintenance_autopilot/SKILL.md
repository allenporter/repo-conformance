---
name: maintenance_autopilot
description: Antigravity-native Evaluator-Optimizer loop for autonomous codebase maintenance, template drift resolution, and dependency health checks across manifest repositories.
---

# 🤖 Maintenance Autopilot Skill (Evaluator-Optimizer Loop)

This skill formalizes the **Antigravity-native Evaluator-Optimizer Loop** for maintaining all repositories in `manifest.yaml`.

It utilizes native Antigravity primitives:
1. **Parallel Worktree Subagents**: Spawns isolated subagents using `invoke_subagent` with `Workspace: "branch"`.
2. **5 Verification Oracles**: Guarantees zero broken code, zero `.rej` patch conflict files, zero unrendered Jinja tags, zero major SemVer regressions, and zero non-bot PR accidental merges.
3. **Pessimistic Verification**: Runs dry-runs and local Oracle tests inside the worktree before committing or pushing to GitHub remotes.

---

## 🛠️ The 4-Step Evaluator-Optimizer Execution Flow

### Step 1: Scan Manifest Health & Detect Drift
Run the health scanner across manifest repositories:
```bash
uv run repo prs --health
```
Identify repos with:
- **Template Drift**: Missing Cruft update PRs or template changes.
- **`🔴 Attention Required` PRs**: Failed CI runs or git patch conflicts (`.rej` files).
- **`🟢 Ready to Merge` PRs**: Safe Renovate/Dependabot patch & minor dependency updates.

---

### Step 2: Auto-Merge Low-Risk Green Dependency Updates
For PRs in the `🟢 Ready to Merge` queue:
```bash
uv run repo prs --renovate --merge --yes
```
* **Oracle Safeguards**:
  * Enforces `author in ["renovate", "renovate[bot]", "dependabot"]`.
  * Enforces `is_major_version_bump == False` (held back unless `--allow-major` is set).

---

### Step 3: Spawn Parallel Subagents in Batches (`Workspace: "branch"`)

> [!IMPORTANT]
> **Strict Concurrency Guard (`MAX_CONCURRENT_SUBAGENTS = 3`)**:
> To prevent context overload and CPU exhaustion, **NEVER spawn more than 3 subagents simultaneously**. Process target repositories in prioritized batches of 1 to 3 repos.

1. **Batch Prioritization**:
   * **Priority 1 (PR Repair)**: Repositories with active CI failures or merge conflicts (`🔴 Attention Required`).
   * **Priority 2 (New Drift PR)**: Repositories with unapplied template drift (`scruft check`).
2. **Sequential Batch Execution**:
   * Launch `invoke_subagent` for **Batch 1 (maximum 3 repos)** using `Workspace: "branch"`.
   * Wait for Batch 1 subagents to complete and report results before launching Batch 2.
3. **Explicit Subagent Action Paths**:
   * **Action Path A: Repair Existing Failing PR** (`🔴 Attention Required`)
     * **Objective**: Fix merge conflicts (`.rej` files) or lint/test failures on an open PR branch.
     * **Execution**: Checkout failing PR branch in worktree ➔ Apply `cruft_resolution` skill ➔ Resolve conflicts/failures ➔ Verify Oracles ➔ Push fix via `git push --force-with-lease`.
   * **Action Path B: Create New Template Update PR** (Template Drift)
     * **Objective**: Generate a new Cruft update PR when template changes land.
     * **Execution**: Run `scruft update` in worktree ➔ Verify Oracles ➔ Commit to `cruft-update` branch ➔ Open PR via `gh pr create`.

4. **Verification Oracles Protocol**:
   Each subagent must run the standard repository scripts locally inside its worktree before pushing:
   1. **CI/Unit Test Oracle**: `./script/test` passes cleanly.
   2. **Linter Oracle**: `./script/lint` passes cleanly.
   3. **Patch Conflict Oracle**: `find . -name '*.rej'` returns 0 conflict files.
   4. **Template Syntax Oracle**: `grep -rn 'cookiecutter\.' .` returns 0 unrendered Jinja tags.
   5. **SemVer Boundary Oracle**: Major version bumps held back unless `--allow-major` is specified.
   * **Self-Correction Loop**: If any Oracle fails, read log tracebacks, fix the underlying code contract in the worktree, and re-run `./script/test` and `./script/lint`.
   * **Push Gate**: **Only when all 5 Oracles pass 100% green**, push the clean branch to `origin` and report status to the orchestrator.

---

### Step 4: Compile Summary Report
Aggregate status from all subagents and compile a concise summary report for the user detailing:
- 🟢 Merged dependency PRs.
- 🛠️ Successfully repaired & force-pushed template PRs.
- 🛑 Repositories requiring human design decisions.

---

## ⏰ Scheduling Background Scans

To set a background recurring timer using the Antigravity `schedule` tool:
* **Cron Expression**: Set `CronExpression="0 0 * * *"` with Prompt `"Run maintenance_autopilot scan on manifest repos"`.
