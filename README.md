# repo-conformance
Conformance tests for all of my git repositories.


## Development

```shell
$ python3 -m venv venv
$ source venv/bin/activate
```

## Usage

The `repo` tool uses a `manifest.yaml` to describe all the git repos in scope.

The `repo list` command verifies the manifest file can be parsed correctly:
```
$ repo list
name: pyrainbird user: allenporter
name: flux-local user: allenporter
name: repo-conformance user: allenporter
```

Running conformance checks can be done with the `repo check` command:
```
$ repo check
pyrainbird:
  worktree:
    ruff: Found flake8 config in setup.cfg; switch to ruff

flux-local:
  worktree:
    ruff: Ruff hooks configuration mismatch:
  - id: ruff
+   args:
+   - --fix
+   - --exit-non-zero-on-fix
```
