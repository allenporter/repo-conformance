# repo-conformance

Conformance tests for all of my git repositories. Conformance tests include
things like:
- A cruft managed repository is up to date
- The github settings are in sync (e.g. specific project settings enabled/disabled)


## Development

```shell
$ uv venv
$ source .venv/bin/activate
$ uv pip install -r requirements_dev.txt
```

## Usage

The `repo` tool uses a `manifest.yaml` to describe all the git repos in scope.

The `repo list` command verifies the manifest file can be parsed correctly:
```bash
$ repo list
name: pyrainbird user: allenporter
name: flux-local user: allenporter
name: repo-conformance user: allenporter
```

Running conformance checks can be done with the `repo check` command:
```bash
$ repo check
rtsp-to-webrtc-client:
  worktree:
    cruft: Repo is out of date, expected ae5501352e9a6fe363996818fc2b4c82f5816450, got 6035ef7fa54ecaf83d0593a553074cf952172437

synthetic-home:
  worktree:
    cruft: Repo is out of date, expected ae5501352e9a6fe363996818fc2b4c82f5816450, got 374e42a1098294fb8c98b8bfe7554b684a7ad14d
```

Review the list of managed github repos and determine which are managed by
`repo_conformance` and which are not:

```bash
$ repo list_repos
  name: cookiecutter-home-assistant-custom-component user: allenporter
  name: cookiecutter-python user: allenporter
  name: devpod-workspaces user: allenporter
  name: esphome-projects user: allenporter
* name: flux-local user: allenporter
  name: functionary-server user: allenporter
* name: gcal_sync user: allenporter
...
```
