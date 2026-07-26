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

### Step 3: Spawn Parallel Subagents in Isolated Worktrees (`Workspace: "branch"`)
For any repository marked `🔴 Attention Required` or needing template updates:

1. Use `invoke_subagent` with `Workspace: "branch"` to create an isolated git worktree.
2. Pass the **`cruft_resolution`** skill to each subagent.
3. **Subagent Execution Protocol**:
   * Run `scruft update` or resolve git patch conflicts in the isolated worktree.
   * **Execute the 5 Verification Oracles locally**:
     1. **CI/Unit Test Oracle**: `pytest` unit test suite passes cleanly.
     2. **Linter Oracle**: `ruff check` & `ty check` pre-commit linters pass.
     3. **Patch Conflict Oracle**: `find . -name '*.rej'` returns 0 conflict files.
     4. **Template Syntax Oracle**: `grep -rn 'cookiecutter\.' .` returns 0 unrendered Jinja tags.
     5. **SemVer Boundary Oracle**: `--allow-major` guard enforced.
   * **Self-Correction Loop**: If any Oracle fails, read the log traceback, fix the root cause in the worktree, and re-evaluate.
   * **Push Gate**: **Only when all 5 Oracles pass 100% green**, push the clean branch to `origin` via `git push --force-with-lease` and open/update the PR.

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
