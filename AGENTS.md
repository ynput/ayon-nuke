# Copilot instructions for ayon-nuke

## Repository scope

This repository is the AYON integration addon for Foundry Nuke. It contains:

- Client-side Python loaded inside Nuke under `client/ayon_nuke/`.
- Server-side AYON settings models and defaults under `server/settings/`.
- Packaging and release metadata in `package.py` and `create_package.py`.
- MkDocs documentation configuration under `docs/`, `mkdocs.yml`, and
  `mkdocs_hooks.py`.

The client code depends on the Nuke Python API and AYON packages. Most client
modules cannot be imported or exercised in a normal Python interpreter without
the Nuke/AYON runtime.

Remote Github repository origin url is https://github.com/ynput/ayon-nuke

## Build, lint, and test commands

Use Python 3.9+ for the addon packaging script. The documentation lockfile
requires Python 3.11+.

```bash
# Lint the repository (same tool used by GitHub Actions)
ruff check .

# Check formatting or format changed Python files
ruff format --check .
ruff format path/to/file.py

# Build a distributable addon zip in ./package/
python create_package.py

# Build the unpacked server package instead of a zip
python create_package.py --skip-zip

# Extract only the client addon files to a development directory
python create_package.py --only-client --output /path/to/output

# Build the documentation
uv sync
uv run mkdocs build

# Serve documentation locally
uv run mkdocs serve
```

There is no checked-in pytest/unittest test suite or test runner configuration.
For a focused validation, run Ruff against the changed file or package the
addon with `python create_package.py`; Nuke behavior requires validation in a
compatible Nuke + AYON environment.

`create_package.py` updates `client/ayon_nuke/version.py` from the version in
`package.py`, includes server files directly, and places the client code in
`private/client.zip`. The output package directory is purged when the target
package/version directory already exists.

## Architecture

### Addon startup and host registration

`client/ayon_nuke/addon.py` defines `NukeAddon`, the AYON host addon. It
configures `NUKE_PATH`, prepends the vendored dependencies to `PYTHONPATH`,
sets logging defaults, and removes environment values that interfere with
Nuke. `client/ayon_nuke/startup/init.py` creates and installs `NukeHost`.
`startup/menu.py` configures the GUI menus and callbacks after the host is
registered. Keep GUI-only work out of startup paths that can run in headless
farm processes.

`client/ayon_nuke/api/pipeline.py` is the central host integration layer. Its
`NukeHost.install()` registers the Pyblish host and the create, load,
inventory, workfile-build, and publish plugin directories. It also implements
the workfile, context, and container interfaces used by AYON. Shared Nuke
operations and node metadata helpers are exposed through `client/ayon_nuke/api/__init__.py`,
especially `api/lib.py`, `api/plugin.py`, and `api/workio.py`.

### Nuke data model

AYON instance and container data is stored on Nuke nodes/root nodes in
dedicated knobs. Use the helpers in `ayon_nuke.api` (`get_node_data`,
`set_node_data`, `containerise`, `parse_container`, and `update_container`)
instead of inventing new metadata formats. Creator nodes, loader containers,
and the workfile root all participate in this metadata model.

### Creator, loader, and workfile plugins

The `plugins/create/` directory defines AYON creators. Creators normally
inherit `NukeCreator`, `NukeWriteCreator`, or an AYON creator base, and declare
an `identifier`, `product_base_type`, `product_type`, and
`settings_category = "nuke"`. Write creators create grouped Write-node
instances and pass configured knobs, pre-nodes, render targets, and staging
paths through the shared helpers in `api/plugin.py` and `api/lib.py`.

The `plugins/load/` directory defines AYON loader plugins. They resolve an
AYON representation, create or update native Nuke nodes, apply colorspace
data, and containerise the node. Loader classes declare supported product
types and representations; preserve their ordering when loaders overlap.

`plugins/create/workfile_creator.py` treats the Nuke root node as the
workfile instance. Workfile I/O is implemented in `api/workio.py`, including
`.nk` handling, current-file state, save/open behavior, and the AYON work
directory.

### Publish pipeline

The `plugins/publish/` modules are Pyblish collectors, validators, extractors,
and integrators. They communicate through `instance.data`, especially
`families`, `productBaseType`, `transientData`, staging directory fields,
render targets, and `representations`. Plugin `order`, `hosts`, and `families`
are functional pipeline contracts, not cosmetic metadata.

Collectors discover Nuke nodes and populate instance data; validators inspect
node state and can expose repair actions; extractors render or export data and
append representations; later integrators handle workfile/version and node
cleanup. Preserve the existing family transitions, representation shape,
colorspace metadata, and frame-range conventions when changing publish code.

### Server settings

`server/settings/main.py` composes the `NukeSettings` model from focused
settings modules for general behavior, callbacks, image I/O, directory
mapping, scripts, gizmos, creators, publishers, loaders, and workfile
building. Each settings model has a matching default structure. Plugin
settings keys commonly use the exact Python class name, so renaming a plugin
requires updating the corresponding server settings model, defaults, and
any client lookup.

Settings models use AYON `BaseSettingsModel` and `SettingsField`; use the
existing enum resolvers, validators, and `ensure_unique_names` patterns for
structured settings. Client plugins read project settings through the
`"nuke"` category and should keep their setting paths aligned with the server
models.

## Codebase conventions

- Prefer the shared `ayon_nuke.api` helpers for Nuke node creation, metadata,
  selection handling, container updates, colorspaces, and workfile operations.
- Keep plugin declarations explicit: `settings_category`, host support,
  families/product types, and Pyblish/loader/creator order must match the
  behavior and server settings.
- Treat Nuke node class names and knob names as runtime API contracts. Account
  for versioned classes such as `Camera3`/`Camera4` using the existing
  matching logic rather than hard-coding one version.
- Keep compatibility imports for supported AYON Core versions where the
  surrounding module already uses them; this addon supports multiple AYON
  Core API locations.
- Use forward-slash-normalized file paths at Nuke/AYON boundaries, while
  retaining `os.pathsep` for environment variable lists.
- Keep vendor code under `client/ayon_nuke/vendor/` out of Ruff changes; it is
  explicitly excluded by `ruff.toml`.
- Follow the repository Ruff configuration: 79-character lines, four-space
  indentation, double-quoted strings, and the enabled `E`, `F`, and `W`
  rules.
- Update both client behavior and server settings/defaults when adding or
  changing a configurable plugin feature.
- Do not assume a normal interpreter can import Nuke modules. Isolate or mock
  Nuke-dependent behavior only in external test/development environments,
  rather than adding runtime fallbacks that hide missing host dependencies.
