# Feature Specification: Nuke USD Camera Loader with Container Update

**Feature Branch**: `sdd_nuke_camera_usd_test` (worktree; no spec-kit git
hook is installed in this repo, so no branch was created by `/speckit.specify`)

**Feature Directory**: `specs/001-nuke-usd-camera-loader`

**Created**: 2026-09-10

**Status**: Draft — clarification resolved (Q1=B)

**Decision**: Q1=B — add a new, separately named `UsdCameraLoaderV2` alongside
`UsdCameraLoader`. The existing loader and identifier remain unchanged for
backward compatibility; the new loader receives a distinct persisted
identifier. The new loader specializes the camera/USD contract while the old
wildcard loader remains available for legacy containers and non-camera USD
products. The two loaders are explicitly labelled and ordered.

**Input**: User description: "New feature: USD camera loader for Nuke with
update capability. Design and implement a Loader plugin in
`client/ayon_nuke/plugins/load/` that loads a USD camera into Nuke and
supports updating an already-loaded USD camera (the AYON 'update' workflow —
re-resolve a representation and update the container in place, preserving
node identity/knobs)."

## Prior Art & Existing Behaviour (evidence)

This repository already contains machinery this feature must build on rather
than duplicate:

- `client/ayon_nuke/plugins/load/load_camera.py` — `AlembicCameraLoader` /
  `FbxCameraLoader`: load abc/fbx cameras from products of base type
  `camera`; both implement `load` / `update` / `switch` / `remove`, use
  `containerise` / `update_container`, imprint version, frame range, source
  and fps metadata, and colour the node by latest-version status.
  `AlembicCameraLoader` creates the newest available `Camera`-family node
  (`Camera3`) with a `Camera2` fallback for older Nuke builds (the
  repository's existing versioned-class handling).
- `client/ayon_nuke/plugins/load/load_camera_usd.py` — `UsdCameraLoader`
  already implements `load` / `update` / `switch` / `remove` for USD files
  (`extensions = {"usd", "usda", "usdc"}`, `product_base_types = {"*"}`,
  `order = 2`) using Nuke's USD-import-capable camera node and resolves the
  camera prim path from the USD stage. It exists on `origin/develop`
  unchanged; **it is prior art, not a blank slate**.
- `client/ayon_nuke/plugins/load/load_model.py`, `load_image.py`,
  `load_clip.py` — the repository's update-capable loader conventions
  (container imprint data, version colouring, `switch` delegating to
  `update`).
- `client/ayon_nuke/api/pipeline.py` — `containerise` (schema
  `ayon:container-3.0`), `parse_container`, `update_container`; the
  container's persisted `loader` value is the loader class name (the loader
  identifier, Article 2).
- `client/ayon_nuke/api/plugin.py` — the `Camera`-family class matching
  convention (regex `^{class_name}\d*$` matches `Camera3`, `Camera4`, …).
- `server/settings/loader_plugins.py` — loader settings model keyed by exact
  class name (e.g. `GeoImportLoader: LoaderEnabledModel`); defaults in
  `DEFAULT_LOADER_PLUGINS_SETTINGS`; client-side application via
  `LoaderPlugin.apply_settings` (ayon-core) reading `nuke.load.<ClassName>`.
  Neither camera loader has a settings entry today.
- `client/ayon_nuke/plugins/load/actions.py` — generic loader actions
  ("Set frame range", …) already cover the `camera` base type; no new GUI is
  needed for camera frame-range control.


## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load a published USD camera into the script (Priority: P1)

A compositor publishes (or receives) a camera product whose representation
is a USD file. From the AYON Loader they pick the USD representation and the
"Load USD Camera" action. The action must produce a working camera node
immediately — no manual node wiring, no manual prim-path entry.

**Why this priority**: Loading is the primary value of the feature; without
it there is nothing to update. It is the independent MVP slice.

**Independent Test**: Load a USD camera representation in a Nuke script;
verify the camera node imports the file, is named per convention, carries
container metadata and renders the published camera.

**Acceptance Scenarios**:

1. **Given** a published camera product with a USD representation,
   **When** the compositor runs the USD camera load action on it in the
   AYON Loader, **Then** a camera node appears in the script that imports
   the camera from that file at the version's frame rate and is immediately
   usable downstream.
2. **Given** the load has completed, **Then** the node is containerised with
   the AYON Nuke container metadata (loader identifier, product name,
   namespace, representation id, project name, version information) and is
   listed in the Scene Inventory.
3. **Given** a USD file containing one or more camera prims, **When** the
   load completes, **Then** the node's imported prim path points at a camera
   prim from that file and the prim path is recorded on the node.
4. **Given** the loaded version is the latest version of the product,
   **Then** the node is coloured with the loader's "latest" colour; when it
   is not the latest, it shows the standard "outdated" colour.
5. **Given** a USD file that contains no camera prim, **When** the load
   action runs, **Then** no half-configured node is left in the script and
   an actionable error explains that the file contains no camera.

### User Story 2 - Update an already-loaded USD camera (Priority: P1)

A compositor has a loaded USD camera container and the product gains a new
version. From the Scene Inventory they update the container (update to
latest / set version). The update happens in place: node identity, position,
connections and user edits survive; only the version-dependent data changes.

**Why this priority**: In-place update with preserved node identity is the
second half of the feature; together with US1 it delivers the full
create → load → update round-trip.

**Independent Test**: Load a USD camera, publish a newer version of the same
product, update the container in Scene Inventory, verify node identity and
camera data.

**Acceptance Scenarios**:

1. **Given** a loaded USD camera container, **When** the compositor updates
   it to a different version of the same product, **Then** the same node
   remains (name, script position, input/output connections and user-modified
   knobs are preserved) and it now reflects the new version's camera data,
   frame rate and file.
2. **Given** the update completed, **Then** the container's recorded
   representation matches the newly loaded one, the version metadata is
   refreshed, and the node colour reflects the new version's latest-status.
3. **Given** the camera prim path was set manually (or auto-detected) and
   still points at a valid camera prim in the new file, **When** updating,
   **Then** that prim path is preserved.
4. **Given** the previously recorded prim path no longer exists or is no
   longer a camera in the new file, **When** updating, **Then** a camera prim
   from the new file is resolved and applied, and the change is reported.
5. **Given** an update that cannot complete (file missing or unreadable, no
   camera prim, USD runtime unavailable), **Then** an actionable error is
   reported and the previously working camera stays usable with its former
   data (no partially applied update, container remains valid).
6. **Given** the update targets the currently loaded representation, **Then**
   the operation is a safe no-op: no duplicate metadata, no loss of edits, no
   node churn.

### User Story 3 - Switch the container to another version or product (Priority: P2)

From the Scene Inventory, a compositor switches a USD camera container to a
different version or a different product of the same kind (the "switch"
workflow).

**Why this priority**: Switching reuses the update behaviour; it adds
coverage but is not required for the MVP.

**Independent Test**: Load a USD camera, switch it to another version or
product in Scene Inventory, verify the container follows the switch.

**Acceptance Scenarios**:

1. **Given** a loaded USD camera container, **When** the compositor switches
   it to another version or product, **Then** the loader resolves the new
   representation through the same update path and the node is updated in
   place.
2. **Given** the switch completed, **Then** the container metadata records
   the new product/representation and no duplicate node is created.

### User Story 4 - Loader list shows the USD camera loader only where it applies (Priority: P2)

In the AYON Loader, the USD camera loader appears exactly where it should and
is distinguishable from the generic USD loaders.

**Why this priority**: Wrong or cluttered loader lists confuse users and
regressions here (e.g. the USD camera loader appearing for non-camera USD
products it cannot make sense of) are visible every day.

**Independent Test**: Browse a project in the AYON Loader; verify the loader
entries and their order for USD representations and for non-USD
representations.

**Acceptance Scenarios**:

1. **Given** a representation with a USD extension, **When** the Loader
   lists compatible actions, **Then** the USD camera loader is present with
   its own label/icon and is distinguishable from generic USD loaders.
2. **Given** a representation without a USD extension, **When** the Loader
   lists compatible actions, **Then** the USD camera loader is not offered.
3. **Given** several loaders accept the same USD representation, **When** the
   Loader sorts actions, **Then** the USD camera loader has an explicit,
   deterministic position (no order tie with another loader accepting the
   same context).

### User Story 5 - Remove a USD camera container (Priority: P3)

A compositor removes the loaded USD camera from the Scene Inventory; the
script returns to its previous state.

**Why this priority**: Removal is expected inventory behaviour and cheap; it
completes the loader lifecycle.

**Independent Test**: Load a USD camera, remove the container, verify no
metadata or orphan nodes remain.

**Acceptance Scenarios**:

1. **Given** a loaded USD camera container, **When** the compositor removes
   it, **Then** the camera node is deleted from the script and no AYON
   metadata or orphan nodes remain.

### Edge Cases

- The representation file is missing or unreadable at load time.
- The USD file opens but contains no camera prim.
- The USD file contains multiple camera prims — resolution must be
  deterministic and recorded.
- The recorded prim path is still set but points at a non-camera prim or a
  prim that does not exist in the new file.
- The USD Python API is not available in the running Nuke build — the loader
  must remain discoverable and fail with an actionable message instead of
  silently disappearing from the loader list.
- The running Nuke build has no USD-import-capable camera class.
- Version attributes (`fps`, `frameStart`/`frameEnd`) are missing — fall back
  to the script's frame rate instead of failing.
- The node was renamed by the user after loading — update/switch/remove must
  target the container node itself, not a name-derived lookup.
- An exception occurs mid-update — the container must stay a valid container
  with its previous data.
- Repeated updates must not grow or duplicate the container metadata
  (known failure class in this addon: "avalon knob keeps growing on every
  version update").
- Mixed abc/fbx + USD cameras in one script (already a known Nuke pain point
  in `AlembicCameraLoader`) — the new loader must not make it worse and must
  not break existing abc/fbx containers.

## Requirements *(mandatory)*

### Functional Requirements

**Loading**

- **FR-001**: The loader MUST be offered by the AYON Loader for
  representations with extension `usd`, `usda` or `usdc`, and MUST create a
  single Nuke camera node (USD-import-capable `Camera`-family class) that
  imports the camera from the file at the version's frame rate.
- **FR-002**: The created node MUST use a USD-capable class resolved with the
  repository's `Camera`-family matching convention (a `Camera`-family class
  like `Camera4` on Nuke 15+); when the running build has no USD-capable
  class, the loader MUST report an actionable error and MUST NOT leave a
  broken node behind.
- **FR-003**: The node name MUST follow the repository convention
  `{product name}_{folder name}` (namespace defaulting to the folder name)
  and MUST be unique in the script (Nuke uniquification accepted).
- **FR-004**: The imported camera prim MUST be resolved from the file: an
  existing prim path that still points at a camera prim in the file MUST be
  preserved; otherwise a camera prim from the file MUST be selected
  deterministically and recorded on the node. A file with no camera prim
  MUST cause an actionable error, not a half-configured node.
- **FR-005**: The loaded node MUST be containerised with the addon's existing
  helper and MUST carry the standard container metadata: loader identifier
  (the loader's class name), product name, namespace, representation id,
  project name, and the version information other Nuke loaders imprint
  (version number, frame range, source, fps).
- **FR-006**: The node MUST be coloured by latest-version status using the
  repository convention (latest = loader's `node_color`, otherwise the
  standard "outdated" colour).

**Updating**

- **FR-007**: A loaded USD camera container MUST be updatable in place: the
  loader re-resolves the representation for the chosen version and applies it
  to the existing node without recreating or renaming it — node identity,
  script position, input/output connections and user-modified knobs MUST be
  preserved.
- **FR-008**: An update MUST refresh everything that depends on the
  representation: file path, frame rate (version fps with script-fps
  fallback), prim-path resolution, version metadata (representation id,
  version, frame range, source, fps) and latest-version colour.
- **FR-009**: An update MUST make the node reflect the new file immediately
  (the same validation/reload step used at load time), so no manual reload or
  scene reopen is required.
- **FR-010**: Updating to the already-loaded representation MUST be a safe
  no-op, and repeated updates MUST NOT grow or duplicate the container
  metadata (bounded size).
- **FR-011**: When an update cannot complete (missing/unreadable file, no
  camera prim, USD unavailable), the loader MUST report an actionable error
  and leave the container valid with its previously working state.
- **FR-012**: Switching the container to a different version or product
  (Scene Inventory switch) MUST resolve through the same update behaviour
  (`switch` delegates to `update`, per repository convention).

**Removal**

- **FR-013**: Removing the container MUST delete the loaded camera node
  without leaving AYON metadata or orphan nodes behind.

**Filtering and ordering**

- **FR-014**: The loader MUST keep accepting the USD camera files in use
  today (extensions `usd`, `usda`, `usdc`; representation-name wildcard) and
  MUST NOT reduce the accepted product scope relative to current behaviour —
  USD products that are not labelled `camera` but contain a usable camera
  (e.g. USD shots) MUST remain loadable as cameras.
- **FR-015**: The loader MUST be distinguishable in the Loader list (label,
  icon, colour) and MUST have an explicit `order` value that does not tie
  with any other loader accepting the same context — specifically not with
  `GeoImportLoader` (`order = 2` today); the before/after values MUST be
  recorded in the plan.

**Settings (Article 3)**

- **FR-016**: The loader's configuration MUST be exposed under the addon's
  `load` settings group keyed by the exact loader class name. Following the
  existing `LoaderEnabledModel` pattern used by `GeoImportLoader` /
  `GeoReferenceLoader`, the settings SHOULD be limited to an `enabled`
  toggle with defaults registered in `DEFAULT_LOADER_PLUGINS_SETTINGS` — the
  loader has no mandatory options beyond that. Renaming any existing
  settings field (there are none for this loader today) would require a
  versioned conversion in `server/settings/conversion.py`.

### Key Entities

- **Representation**: the versioned artifact record the loader consumes; its
  resolved file path and the version's attributes (fps, frame range, source)
  drive the loaded node.
- **Container**: the imprinted Nuke camera node tying the node to a
  representation; managed by the Scene Inventory; its persisted loader
  identifier (class name) selects this loader for update/switch/remove.
- **Camera prim**: the USD prim of type `Camera` inside the file that the
  node imports; its path is recorded on the node and preserved across
  updates while valid.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With no manual node setup or prim-path entry, a compositor
  loads a published USD camera and the node's framing and lens match the
  published camera (verified by a reviewer in Nuke).
- **SC-002**: Updating to another version preserves node identity in 100% of
  cases — same node object, name, position, connections and user edits; the
  node is never replaced or renamed by the update.
- **SC-003**: Ten consecutive updates leave the imprinted container data
  bounded (no growth) and the node functional.
- **SC-004**: Every failure case (missing/unreadable file, no camera prim,
  USD runtime unavailable) produces a user-visible actionable message, and in
  100% of update-failure cases the previously working camera remains usable.
- **SC-005**: In the Loader list, the USD camera loader appears exactly once
  for USD representations, never appears for non-USD representations, and
  has a deterministic position relative to the generic USD loaders.
- **SC-006**: Existing camera loading (abc/fbx) and all other loaders keep
  their current identifiers, behaviour and positions — no regression.

## Assumptions

- The running Nuke build has USD support and a USD-import-capable camera
  class (Nuke 15+); older builds get an actionable error (FR-002).
- "Update" means re-resolving the representation of the same product at the
  chosen version via Scene Inventory (standard AYON container update).
  Version/product switching is covered by the same code path through the
  loader's `switch` alias — no separate switching mechanism is needed
  (evidence: `load_image.py`, `load_model.py`, `load_camera.py`).
- No GUI work: load/update/switch/remove are surfaced by the existing AYON
  Loader and Scene Inventory; `startup/menu.py` gets no new entries; generic
  camera-applicable loader actions already exist in
  `plugins/load/actions.py`.
- No colorspace handling applies to camera nodes (cameras carry no pixel
  data; neither existing camera loader touches colorspace).
- The loader is interactive (used from the UI), but its module import must
  never break addon import at launcher time (it lives under `plugins/load/`
  which is host-only) and USD-API absence must degrade to an actionable
  message rather than a discovery crash.
- USD camera products originate from other AYON host addons; this feature
  changes nothing about how cameras are published (no extractor/integrator
  change).
- The loader's class-name-based identifier is a persisted contract: any
  rename or new parallel class must be justified and handled explicitly
  (see Q1 below), because containers store the class name.

## Resolved Open Questions (answers from investigation)

1. **What does "update" cover?** The standard container update —
   re-resolving the representation of the same product at the selected
   version — plus, via the loader's `switch` alias, switching to another
   version/product through Scene Inventory. Both preserve the container's
   node. Resolved from AYON Scene Inventory semantics and the repo's loader
   conventions.
2. **Is GUI needed?** No. AYON already provides the Loader (menus wired in
   `startup/menu.py` via `host_tools.show_loader`) and Scene Inventory; the
   right-click/loader actions for cameras ("Set frame range") already exist.
   No new menu entries.
3. **Which node class?** A USD-import-capable `Camera`-family class resolved
   with the existing convention (`Camera4` on Nuke 15+). The feature must NOT
   merge with `AlembicCameraLoader`/`FbxCameraLoader`: those are for abc/fbx
   files, their identifier is persisted in existing containers, and merging
   would change an existing pipeline contract (Article 2). Separate loaders,
   shared conventions.
4. **What filtering should the loader accept?** In this codebase a loader's
   compatibility is decided by ayon-core's `is_compatible_loader` from
   `product_base_types`/`product_types`, `representations` and `extensions`
   — there is no `representation_matches` hook. The legacy loader retains
   `product_base_types = {"*"}` and `representations = {"*"}`; the new
   `UsdCameraLoaderV2` accepts `product_base_types = {"camera"}` and
   `representations = {"usd"}`, with all three USD extensions (FR-014).

---

## AYON impact analysis

- **Settings impact (Article 3)**: if FR-016 is accepted, this feature adds
  one loader settings entry — `server/settings/loader_plugins.py` gains
  `UsdCameraLoaderV2: LoaderEnabledModel` in `LoaderPluginsModel` plus its
  default in `DEFAULT_LOADER_PLUGINS_SETTINGS` (`{"enabled": True}`). `main.py` needs no
  change (`load` is already composed from that defaults dict). Client-side
  lookup stays `project_settings["nuke"]["load"]["<ClassName>"]` via
  ayon-core `LoaderPlugin.apply_settings`. Additive only — no renames, so no
  `_convert_*` migration is required. The existing camera loaders are
  explicitly left without settings entries (no regression).
- **Host constraints (Article 7)**: the feature runs inside Nuke (host API
  and the USD Python API at module scope). The file lives under
  `client/ayon_nuke/plugins/load/`, which is imported only at Nuke runtime,
  so `addon.py` (launcher-time) stays untouched and importable pre-Nuke.
  The USD API import must be guarded so plugin discovery keeps the loader
  listed with an actionable message when USD is unavailable (discovery
  currently records a crashed module, which silently drops the loader). No
  GUI/farm-path changes; headless publish paths are untouched.
- **Pipeline contracts touched (Article 2)**:
  - Loader identifier persisted in containers (`loader` knob value): existing
    `UsdCameraLoader` remains unchanged; the additive new identifier is
    `UsdCameraLoaderV2` (Q1-B). Existing containers keep resolving to the old
    class; new containers use the new class.
  - Legacy `UsdCameraLoader` contracts remain unchanged: product base types
    `{"*"}`, representations `{"*"}`, and extensions
    `{"usd", "usda", "usdc"}`.
  - New `UsdCameraLoaderV2` contracts: product base types
    `{"camera"}`, representations `{"usd"}`, and extensions
    `{"usd", "usda", "usdc"}`.
  - Pyblish `order`/`hosts`/`families` touched by other plugins: none.
  - Loader action `order`: `2` → proposed `1` (free slot between the
    default-0 geometry path and `GeoImportLoader`'s `2`/`GeoReferenceLoader`'s
    `3`), removing the current tie at `2`; the plan MUST record the
    before/after values (FR-015).
  - No creator, extractor, integrator or representation-production changes.
- **Addon anatomy (Article 1)**: stays entirely inside the existing
  `client/ayon_nuke/plugins/load/` + `server/settings/` shape; no new
  top-level directory. `client/ayon_nuke/vendor/` untouched (Article 5/6).
- **Verification ladder (Article 8)**: this repo has no test suite (no
  `tests/`, no `[tool.pytest.ini_options]`) — do not add one. Automated
  gates: `ruff check .`, `ruff format --check .`,
  `python create_package.py --skip-zip`. Manual Nuke + AYON validation by a
  human reviewer: create a camera (existing `CreateCamera`) → publish →
  load the USD camera → modify the script (rename node, add connections,
  set a custom prim path) → publish a new version → update via Scene
  Inventory → verify identity/connections/edits preserved and camera data
  refreshed → verify latest-version colour on both load and update → switch
  to another version/product → remove the container → repeat the round-trip
  with a USD camera containing multiple prims and with a version whose USD
  file has no camera prim (error path) → verify loader list position against
  `GeoImportLoader`/`GeoReferenceLoader` and that abc/fbx camera loading
  still works.

---

## Decision Record (Q1 — resolved as B)

The legacy loader `UsdCameraLoader` in `load_camera_usd.py` already exists on
`origin/develop` with the same identifier, load/update/switch/remove, USD
extensions, wildcard product scope and `order = 2`. Q1=B selects an additive
new class, `UsdCameraLoaderV2`, rather than modifying that persisted contract.
The user request says "implement a new Loader plugin". These two facts
conflict, and the choice changes a persisted pipeline contract, so it is
surfaced here rather than guessed.

**Decision**: B — introduce `UsdCameraLoaderV2` alongside the existing loader.
The old `UsdCameraLoader` remains available for existing containers; the new
class uses a distinct persisted identifier and specialized camera/USD
compatibility, so the two loader choices are not indistinguishable.
