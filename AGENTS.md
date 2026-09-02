# Copilot instructions for ayon-nuke

## General AYON instructions

Generic AYON addon instructions are distributed separately. When needed,
first look for and follow in case worktree was setupped correctly with git hook:

`.agents-main/AGENTS.md`

The directory is outside this repository root and contains the
organization-level agentic skills and instructions.


## Nuke-specific repository details

This repository integrates AYON with Foundry Nuke. Client code is under
`client/ayon_nuke/`, server settings are under `server/settings/`, and package
creation is handled by `package.py` and `create_package.py`.

The client depends on the Nuke Python API. Do not assume Nuke-dependent
modules can be imported or exercised in a normal Python interpreter.

The remote repository is https://github.com/ynput/ayon-nuke.

## Nuke-specific validation

Use Python 3.9+ for addon packaging. The documentation lockfile requires
Python 3.11+.

```bash
ruff check .
ruff format --check .
python create_package.py
python create_package.py --skip-zip
python create_package.py --only-client --output /path/to/output
uv sync
uv run mkdocs build
uv run mkdocs serve
```

There is no checked-in test suite. Nuke behavior requires validation in a
compatible Nuke + AYON environment.

`create_package.py` updates `client/ayon_nuke/version.py` from `package.py`,
includes server files directly, and places the client code in
`private/client.zip`.

## Nuke integration architecture

`client/ayon_nuke/addon.py` defines `NukeAddon`. It configures `NUKE_PATH`,
prepends vendored dependencies to `PYTHONPATH`, sets logging defaults, and
removes environment values that interfere with Nuke.

`client/ayon_nuke/startup/init.py` creates and installs `NukeHost`.
`startup/menu.py` configures GUI menus and callbacks after host registration.
Keep GUI-only work out of startup paths that can run in headless farm
processes.

`client/ayon_nuke/api/pipeline.py` is the central host integration layer.
`NukeHost.install()` registers the Pyblish host and the create, load,
inventory, workfile-build, and publish plugin directories. It also implements
the workfile, context, and container interfaces used by AYON.

Shared Nuke operations and node metadata helpers are exposed through
`client/ayon_nuke/api/__init__.py`, especially `api/lib.py`, `api/plugin.py`,
and `api/workio.py`.

## Nuke data model

AYON instance and container data is stored on Nuke nodes and root nodes in
dedicated knobs. Use `ayon_nuke.api` helpers such as `get_node_data`,
`set_node_data`, `containerise`, `parse_container`, and `update_container`
instead of inventing metadata formats.

Creator nodes, loader containers, and the workfile root all participate in
this metadata model.

## Nuke creators, loaders, and workfiles

Creators normally inherit `NukeCreator`, `NukeWriteCreator`, or an AYON creator
base. Write creators create grouped Write-node instances and pass configured
knobs, pre-nodes, render targets, and staging paths through
`api/plugin.py` and `api/lib.py`.

Loaders resolve AYON representations, create or update native Nuke nodes,
apply colorspace data, and containerise the node. Preserve loader ordering
when supported product types or representations overlap.

`plugins/create/workfile_creator.py` treats the Nuke root node as the workfile
instance. Workfile I/O is implemented in `api/workio.py`, including `.nk`
handling, current-file state, save/open behavior, and the AYON work directory.

## Nuke-specific settings and runtime contracts

`server/settings/main.py` composes `NukeSettings` from focused Nuke settings
modules. Client plugins read project settings through the `"nuke"` category;
keep those paths aligned with the server models and defaults.

Treat Nuke node class names and knob names as runtime API contracts. Account
for versioned classes such as `Camera3` and `Camera4` using existing matching
logic rather than hard-coding one version.

Use forward-slash-normalized paths at Nuke/AYON boundaries, while retaining
`os.pathsep` for environment variable lists.

Keep vendor code under `client/ayon_nuke/vendor/` out of Ruff changes; it is
explicitly excluded by `ruff.toml`.
