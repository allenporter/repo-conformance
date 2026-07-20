---
name: cruft_resolution
description: >
  Use this skill when running template updates (Cruft or Scruft) on custom component repositories and encountering merge conflicts, .rej (reject) files, or failed update errors. This skill guides the agent through setting up an isolated clone and worktree of the target project, manually resolving business logic vs toolchain conflicts, correcting pre-commit config hooks, verifying with bootstrap/test/lint scripts, and pushing the clean update branch.
---

# Cruft Resolution Skill

This skill documents how to resolve conflicts and correctly apply template updates when running Cruft/Scruft update on custom component repositories.

## Overview

When updating a repository using `scruft update` or `cruft update`, conflicts may arise because the target repository has customized files. This generates conflict reject (`.rej`) files, which can cause push or workflow failures.

## Terminology & Workspace Isolation

To prevent confusion between different workspaces and git worktrees during multi-repository maintenance, refer to this glossary:

1. **Orchestrator Workspace (`repo-conformance`)**:
   - Path: `/Users/allen/Development/repo-conformance` (on the host system).
   - Description: The local clone containing `manifest.yaml` and the Python check/update runner scripts.

2. **Subagent Workspace (Orchestrator Worktree)**:
   - Path: Located inside the agent's application directory (e.g., `<appDataDir>/brain/<conversation-id>/`).
   - Description: A git worktree or clone of `repo-conformance` automatically created for the subagent to run the CLI commands in isolation.

3. **Target Project Clone**:
   - Path: A temporary directory created dynamically (e.g., via `tempfile.TemporaryDirectory()`).
   - Description: A clean clone of the repository being updated (e.g., `pyrainbird`) downloaded directly from the GitHub remote.

4. **Target Project Conflict-Resolution Worktree**:
   - Path: `../worktrees/<repo-name>-update` relative to the Target Project Clone.
   - Description: A git worktree of the target project created specifically to resolve template conflicts and run validation scripts.

## Gotchas

- **Auto-Deletion on Failure**: If the `repo-conformance update_repo` run fails, Python automatically cleans up the temporary clone. Any `.rej` files generated during that initial run are permanently lost. You must manually clone the target project and run `scruft update -y` again to regenerate the rejects.
- **Pre-commit Local Hooks**: After template updates, local hooks in `.pre-commit-config.yaml` (such as the `ty check` hook) often break because they lack `uv run` prefixes. Be sure to verify and prefix them with `uv run --no-project`.
- **Double Linting**: Running `./script/lint` the first time may fail but auto-format the files. Always run it a second time if the first run fails to verify that the auto-formatting resolved all issues.

## Standard Resolution Workflow

Always perform this work in an isolated subagent workspace and use a temporary git worktree to avoid polluting or dirtying the active workspace.

> [!TIP]
> Before starting this workflow, create a checklist in `task.md` to track your progress through these steps.

### Set Up the Target Clone
Since the temporary clone created by `repo-conformance update_repo` is automatically deleted on failure, you must first create a new local clone of the target project in the **Subagent Workspace**:
1. Clone the repository from GitHub:
   ```bash
   git clone https://github.com/<user>/<repo-name>.git
   ```
2. Navigate into the cloned directory (which is now your repository root):
   ```bash
   cd <repo-name>
   ```

### Isolate in a Worktree
From the cloned repository root, add a temporary worktree to isolate the conflict resolution:
```bash
git worktree add -b cruft-update ../worktrees/<repo-name>-update origin/main
```
Navigate to the new worktree directory:
```bash
cd ../worktrees/<repo-name>-update
```

### Regenerate and Apply the Update
In the worktree directory, run `scruft` to trigger the template update and regenerate the conflict reject (`.rej`) files:
```bash
scruft update -y
```

### Resolve and Discard File Conflicts
When Cruft fails to apply a template patch cleanly, it generates `.rej` (reject) files containing the hunks it could not merge. Analyze and resolve these conflicts using the following general guidelines:

1. **Custom Implementation Logic (Discard Template Changes)**:
   - If the conflict occurs in custom integration source files or custom test logic (files that define the core functionality of the component rather than the template scaffold), **keep the repository version**.
   - Discard the template changes by checking out the file from `HEAD`:
     ```bash
     git checkout HEAD -- <path/to/conflicted/file>
     ```

2. **Toolchain & Configuration Files (Resolve or Keep Repo Version)**:
   - If the conflict is in standard configuration files (such as `.github/workflows/`, `.pre-commit-config.yaml`, `requirements_dev.txt`, `pyproject.toml`), inspect the reject file (`.rej`).
   - If the conflict is due to the repository already having newer versions or custom configurations, discard the template changes.
   - If the template update contains a required build or pipeline adjustment (like python 3.14 compatibility or a new linter setting), apply the change manually.

3. **Cleanup Reject Files**:
   - Once all conflicts are addressed, find and delete all untracked reject files:
     ```bash
     find . -name "*.rej" -delete
     ```

### Correct the Pre-commit Config
In `.pre-commit-config.yaml`, ensure any local hooks (like the `ty` check hook) are updated to run via `uv run` in the system language:
```yaml
      - id: ty
        name: ty check
        entry: uv run --no-project ty check . --ignore unresolved-import
        language: system
```

### Verify the Updates (Validation Loop)
Validate that the updates compile and pass tests:
1. Run `./script/bootstrap` to install environment dependencies.
2. Run `./script/lint` to check code style.
   - If files are auto-formatted or linting fails, fix the issues and run `./script/lint` again until it passes.
3. Run the test suite:
   ```bash
   ./script/test --snapshot-update
   ```
   - If tests fail, resolve the discrepancies and run the tests again until they pass.

### Commit and Push
Once verification succeeds, commit the changes and push the branch to remote:
```bash
git add .
git commit -m "chore: apply modern toolchain Cruft update"
git push -f origin cruft-update:cruft-update
```
