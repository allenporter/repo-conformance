---
name: cruft_resolution
description: Resolve conflicts during cookiecutter template updates via Cruft or Scruft on custom components.
---

# Cruft Resolution Skill

This skill documents how to resolve conflicts and correctly apply template updates when running Cruft/Scruft update on custom component repositories.

## Overview

When updating a repository using `scruft update` or `cruft update`, conflicts may arise because the target repository has customized files. This generates conflict reject (`.rej`) files, which can cause push or workflow failures.

## Standard Resolution Workflow

Always perform this work in a temporary git worktree to avoid polluting or dirtying the active workspace.

### 1. Isolate in a Worktree
From the repository root, add a temporary worktree:
```bash
git worktree add -b cruft-update ../worktrees/<repo-name>-update origin/main
```

### 2. Apply the Update
In the worktree directory, run `scruft` to trigger the update:
```bash
scruft update -y
```

### 3. Resolve and Discard File Conflicts
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

### 4. Correct the Pre-commit Config
In `.pre-commit-config.yaml`, ensure any local hooks (like the `ty` check hook) are updated to run via `uv run` in the system language:
```yaml
      - id: ty
        name: ty check
        entry: uv run --no-project ty check . --ignore unresolved-import
        language: system
```

### 5. Verify the Updates
Always verify that the updates compile and pass tests:
```bash
# Bootstrap to install environment dependencies
./script/bootstrap

# Lint the codebase (retry once if files were auto-formatted)
./script/lint || ./script/lint

# Run the test suite, updating any formatted snapshot files automatically
./script/test --snapshot-update
```

### 6. Commit and Push
Once verification succeeds, commit the changes and push the branch to remote:
```bash
git add .
git commit -m "chore: apply modern toolchain Cruft update"
git push -f origin cruft-update:cruft-update
```
