"""Action to update a github repos using scruft."""

import pathlib
import tempfile
import logging
from contextlib import contextmanager
from argparse import ArgumentParser, BooleanOptionalAction
from collections.abc import Generator
from argparse import _SubParsersAction as SubParsersAction
from typing import cast
from subprocess import PIPE, run

import scruft
import git

from .manifest import parse_manifest, Repo

_LOGGER = logging.getLogger(__name__)

CLONE_URL_FORMAT = "https://github.com/{user}/{repo}.git"
CRUFT_BRANCH = "cruft-update"
PR_TITLE = "Apply cruft updates"
PR_BODY = "Automatically generated PR from `repo-conformance` to apply updates using `scruft`."
COMMIT_MSG = "Apply cruft updates"


@contextmanager
def repo_working_dir(
    repo: Repo, worktree: pathlib.Path | None
) -> Generator[git.Repo, None, None]:
    """Open the repository locally."""
    if worktree:
        yield git.Repo.init(worktree)
        return

    # Checkout the repo locally
    with tempfile.TemporaryDirectory() as tmpdir:
        git_repo = git.Repo.init(tmpdir)
        origin = git_repo.create_remote(
            "origin", CLONE_URL_FORMAT.format(user=repo.user, repo=repo.name)
        )
        if not origin.exists():
            raise ValueError("Failure to setup repo origin")
        origin.fetch()
        if not origin.refs.main:
            raise ValueError("Git repo does not have main branch")
        main = git_repo.create_head("main", origin.refs.main)
        main.set_tracking_branch(origin.refs.main)
        main.checkout()

        yield git_repo


def verify_gh_auth() -> None:
    """Verify the user is logged into the Github CLI."""
    _LOGGER.debug("Verifying user is logged into Github CLI")
    result = run(
        ["gh", "auth", "status"],
        check=True,
        stdout=PIPE,
        stderr=PIPE,
    )
    _LOGGER.debug("gh auth status: %s", result.stdout.decode())


def create_cruft_branch(git_repo: git.Repo) -> None:
    """Create a branch for the cruft update."""
    _LOGGER.debug("Creating a branch for the cruft update")
    branch = git_repo.create_head(CRUFT_BRANCH)
    branch.checkout()
    if git_repo.active_branch.name != CRUFT_BRANCH:
        raise ValueError(
            f"Local clone of repository is not tracking cruft-update branch: {git_repo.active_branch.name}"
        )


def resolve_mypy_to_ty_transition(working_dir: pathlib.Path) -> None:
    """Resolve conflicts and clean up .rej files from the mypy to ty transition."""
    import re

    def clean_conflicts_and_read(file_path: pathlib.Path) -> str | None:
        if not file_path.exists():
            return None
        content = file_path.read_text()
        conflict_pattern = (
            r"<<<<<<< ours\n[\s\S]*?\n=======\n([\s\S]*?)\n>>>>>>> theirs"
        )
        if re.search(conflict_pattern, content):
            content = re.sub(conflict_pattern, r"\1", content)
            file_path.write_text(content)
            _LOGGER.info("Resolved merge conflicts in favor of theirs in %s", file_path)
        return content

    # 1. Update .pre-commit-config.yaml
    pre_commit_file = working_dir / ".pre-commit-config.yaml"
    content = clean_conflicts_and_read(pre_commit_file)
    if content is not None:
        mypy_pattern = """  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: script/run-mypy.sh
        language: script
        types: [python]
        require_serial: true"""
        ty_replacement = """  - repo: local
    hooks:
      - id: ty
        name: ty check
        entry: ty check . --ignore unresolved-import
        language: python
        pass_filenames: false"""
        if mypy_pattern in content:
            content = content.replace(mypy_pattern, ty_replacement)
            pre_commit_file.write_text(content)
            _LOGGER.info(
                "Successfully replaced mypy pre-commit hook with ty check in %s",
                pre_commit_file,
            )
        else:
            pattern = r" {2}- repo: local\s+hooks:\s+ {6}- id: mypy\s+name: mypy\s+entry: script/run-mypy.sh\s+language: script\s+types: \[python\]\s+require_serial: true"
            if re.search(pattern, content):
                content = re.sub(pattern, ty_replacement, content)
                pre_commit_file.write_text(content)
                _LOGGER.info(
                    "Successfully regex-replaced mypy pre-commit hook with ty check in %s",
                    pre_commit_file,
                )

    rej_file = working_dir / ".pre-commit-config.yaml.rej"
    if rej_file.exists():
        rej_file.unlink()

    # 2. Update requirements_dev.txt
    req_file = working_dir / "requirements_dev.txt"
    content = clean_conflicts_and_read(req_file)
    if content is not None:
        content, count = re.subn(r"mypy==\d+\.\d+\.\d+", "ty==0.0.18", content)
        if count > 0:
            req_file.write_text(content)
            _LOGGER.info(
                "Successfully updated requirements_dev.txt from mypy to ty==0.0.18"
            )

    rej_file = working_dir / "requirements_dev.txt.rej"
    if rej_file.exists():
        rej_file.unlink()

    # 3. Update .gitignore
    gitignore_file = working_dir / ".gitignore"
    content = clean_conflicts_and_read(gitignore_file)
    if content is not None:
        if ".ty_cache/" not in content:
            if ".DS_Store" in content:
                content = content.replace(".DS_Store", "# ty\n.ty_cache/\n\n.DS_Store")
            else:
                content += "\n# ty\n.ty_cache/\n"
            gitignore_file.write_text(content)
            _LOGGER.info("Successfully added .ty_cache/ to .gitignore")

    rej_file = working_dir / ".gitignore.rej"
    if rej_file.exists():
        rej_file.unlink()

    # 4. Remove script/run-mypy.sh
    mypy_script = working_dir / "script" / "run-mypy.sh"
    if mypy_script.exists():
        mypy_script.unlink()
        _LOGGER.info("Successfully deleted script/run-mypy.sh")

    # 5. Update .github/workflows/lint.yaml
    lint_file = working_dir / ".github" / "workflows" / "lint.yaml"
    content = clean_conflicts_and_read(lint_file)
    if content is not None:
        mypy_lint_pattern = """      - name: Static typing with mypy
        run: |
          mypy --install-types --non-interactive --no-warn-unused-ignores ."""
        ty_lint_replacement = """      - name: Static typing with ty
        run: |
          ty check . --ignore unresolved-import"""
        if mypy_lint_pattern in content:
            content = content.replace(mypy_lint_pattern, ty_lint_replacement)
            lint_file.write_text(content)
            _LOGGER.info(
                "Successfully replaced mypy CI step with ty check in %s", lint_file
            )
        else:
            pattern = r" {6}- name: Static typing with mypy\s+run: \|\s+mypy --install-types --non-interactive --no-warn-unused-ignores \."
            if re.search(pattern, content):
                content = re.sub(pattern, ty_lint_replacement, content)
                lint_file.write_text(content)
                _LOGGER.info(
                    "Successfully regex-replaced mypy CI step with ty check in %s",
                    lint_file,
                )

    rej_file = working_dir / ".github" / "workflows" / "lint.yaml.rej"
    if rej_file.exists():
        rej_file.unlink()

    # 6. Update pyproject.toml
    pyproject_file = working_dir / "pyproject.toml"
    content = clean_conflicts_and_read(pyproject_file)
    if content is not None:
        if "[tool.ty" not in content:
            content += '\n[tool.ty.src]\nexclude = ["tests", "examples"]\n'
            pyproject_file.write_text(content)
            _LOGGER.info(
                "Successfully added [tool.ty.src] exclude config to %s", pyproject_file
            )


def apply_updates(git_repo: git.Repo) -> None:
    """Perform cruft updates in the github repository."""
    _LOGGER.debug("Applying changes from cruft")
    working_dir = pathlib.Path(git_repo.working_dir)
    if not scruft.update(working_dir):
        raise ValueError("Cruft update failed")
    resolve_mypy_to_ty_transition(working_dir)


def commit_changes(git_repo: git.Repo, comit_message: str) -> None:
    """Commit changes to the branch."""
    git_repo.git.add(update=True)
    if git_repo.untracked_files:
        git_repo.git.add(git_repo.untracked_files)
    git_repo.index.commit(comit_message)


def push_and_create_pr(git_repo: git.Repo, dry_run: bool = False) -> str:
    git_repo.remote().push(refspec=f"{CRUFT_BRANCH}:{CRUFT_BRANCH}", force=True)
    _LOGGER.info("Branch '%s' pushed to remote.", CRUFT_BRANCH)
    _LOGGER.info("Creating PR")
    result = run(
        [
            "gh",
            "pr",
            "create",
            "--title",
            PR_TITLE,
            "--body",
            PR_BODY,
            "--head",
            CRUFT_BRANCH,
            "--base",
            "main",
        ],
        cwd=str(git_repo.working_dir),
        stdout=PIPE,
        stderr=PIPE,
    )
    if result.returncode != 0:
        stderr_decoded = result.stderr.decode()
        if "already exists" in stderr_decoded:
            _LOGGER.info("Pull request already exists for this branch.")
            import re

            urls = re.findall(r"https://github.com/[^\s]+", stderr_decoded)
            return urls[0] if urls else "PR already exists"
        raise ValueError(
            "Error when creating PR with `gh pr create`: " + stderr_decoded
        )
    return result.stdout.decode()


class UpdateRepoAction:
    """Update repo action."""

    @classmethod
    def register(cls, subparsers: SubParsersAction) -> ArgumentParser:
        args = cast(
            ArgumentParser,
            subparsers.add_parser("update_repo", help="Update a github repository."),
        )
        args.add_argument(
            "repo",
            help="The name of the repo to check, or all if omitted",
            type=str,
            nargs="?",
        )
        args.add_argument(
            "--worktree",
            help="The local worktree path to use instead of cloning the repo",
            type=pathlib.Path,
            required=False,
        )
        args.add_argument(
            "--dry-run",
            help="Run without pushing and sending a PR.",
            default=False,
            action=BooleanOptionalAction,
        )
        args.set_defaults(cls=UpdateRepoAction)
        return args

    def run(
        self,
        repo: str,
        worktree: pathlib.Path | None = None,
        dry_run: bool = False,
        **kwargs,  # pylint: disable=unused-argument
    ) -> None:
        """Async Action implementation."""
        manifest = parse_manifest()
        # Before attempting to send a PR make sure we're able to leverage gh credentials
        verify_gh_auth()

        projects = 0
        updated = 0
        already_up_to_date = 0

        for manifest_repo in manifest.repos:
            if "cruft" not in manifest_repo.checks.include:
                _LOGGER.info(
                    "Skipping repo %s; cruft not in include checks.", manifest_repo
                )
                continue
            if repo and manifest_repo.name != repo:
                continue
            if not manifest_repo.user:
                manifest_repo.user = manifest.user

            print(f"Updating repo: {manifest_repo}")
            with repo_working_dir(manifest_repo, worktree) as git_repo:
                if git_repo.is_dirty() or git_repo.untracked_files:
                    raise ValueError(
                        "Local clone of repository is dirty or has untracked files"
                    )

                projects += 1
                create_cruft_branch(git_repo)
                apply_updates(git_repo)
                if not git_repo.is_dirty():
                    already_up_to_date += 1
                    _LOGGER.info(
                        "No changes detected after scruft update; Repo is up to date."
                    )
                    continue
                updated += 1

                commit_changes(git_repo, COMMIT_MSG)
                if dry_run:
                    print("Dry run complete. Changes applied locally.")
                    continue

                url = push_and_create_pr(git_repo)
                print(f"Created pull request: {url}")

        print(
            f"Updated {updated} of {projects} projects ({already_up_to_date} already up to date)."
        )
