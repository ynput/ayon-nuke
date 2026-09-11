# Tasks: Nuke USD Camera Loader with Container Update

**Input**: Design documents from `specs/001-nuke-usd-camera-loader/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: No test tasks. This repository has no test suite; the specification requires lint, format, packaging, and manual Nuke + AYON validation.

## Phase 1: Setup

- [ ] T001 Confirm the Q1=B additive contract and implementation paths in `specs/001-nuke-usd-camera-loader/plan.md`, `specs/001-nuke-usd-camera-loader/contracts/loader-contract.md`, and the repository working tree
- [ ] T002 [P] Audit current `UsdCameraLoader`, `GeoImportLoader`, and settings class names in `client/ayon_nuke/plugins/load/load_camera_usd.py` and `server/settings/loader_plugins.py` before editing

## Phase 2: Foundational

- [ ] T003 Add an optional USD runtime import guard and actionable availability helper in `client/ayon_nuke/plugins/load/load_camera_usd.py` without changing the legacy `UsdCameraLoader` identifier or compatibility attributes
- [ ] T004 Add deterministic USD stage/camera-prim resolution helpers in `client/ayon_nuke/plugins/load/load_camera_usd.py`, including valid-existing-prim preservation and no-camera error handling
- [ ] T005 Add shared node-knob capture/restore and runtime USD-camera-node validation helpers in `client/ayon_nuke/plugins/load/load_camera_usd.py` for transactional updates and Camera-family version handling

## Phase 3: User Story 1 — Load a published USD camera (P1) 🎯 MVP

**Goal**: Add a distinct specialized loader for camera products with `usd` representations while preserving the legacy wildcard loader.

**Independent Test**: In compatible Nuke + AYON, load a `camera` product with a `usd` representation and verify a usable, containerised USD camera node with a resolved camera prim and version metadata.

- [ ] T006 [US1] Add the new `UsdCameraLoaderV2` class in `client/ayon_nuke/plugins/load/load_camera_usd.py` with distinct identifier, label, icon/colour, `product_base_types = {"camera"}`, `representations = {"usd"}`, USD extensions, `order = 1`, and `settings_category = "nuke"`
- [ ] T007 [US1] Implement `UsdCameraLoaderV2.load` in `client/ayon_nuke/plugins/load/load_camera_usd.py` using the existing Camera-family creation helper, normalized representation path, frame-rate fallback, resolved prim path, latest-version colour, and `containerise` metadata
- [ ] T008 [US1] Ensure `UsdCameraLoaderV2.load` deletes any partially created node and raises an actionable error for missing files, unavailable USD support, unsupported Nuke camera knobs/classes, unreadable stages, or files without camera prims in `client/ayon_nuke/plugins/load/load_camera_usd.py`

## Phase 4: User Story 2 — Update an already-loaded USD camera (P1)

**Goal**: Update the new container in place while preserving node identity and user edits, with rollback on failure.

**Independent Test**: Load a V2 container, alter its name/position/connections/user knobs, update to a newer representation, and verify the same node and edits survive while file, prim path, frame rate, metadata and colour refresh.

- [ ] T009 [US2] Implement transactional `UsdCameraLoaderV2.update` in `client/ayon_nuke/plugins/load/load_camera_usd.py`, validating the new USD stage/prim before mutation and restoring node/container state if mutation or validation fails
- [ ] T010 [US2] Refresh only representation-dependent V2 node values and AYON metadata through `update_container` in `client/ayon_nuke/plugins/load/load_camera_usd.py`; preserve node identity, name, position, connections and unrelated user knobs across repeated updates
- [ ] T011 [US2] Implement `UsdCameraLoaderV2.switch`, `remove`, and V2-specific undo labels in `client/ayon_nuke/plugins/load/load_camera_usd.py`, delegating switch to update and removing only the container node

## Phase 5: User Story 3 — Switch version or product (P2)

**Goal**: Cover Scene Inventory switching through the same in-place update path.

**Independent Test**: Switch a V2 container to another version/product in Scene Inventory and verify one existing node reflects the selected representation.

- [ ] T012 [US3] Verify and, if needed, harden V2 `switch` context handling for another version/product while preserving the container's node object and AYON metadata contract in `client/ayon_nuke/plugins/load/load_camera_usd.py`

## Phase 6: User Story 4 — Filtering and deterministic loader list (P2)

**Goal**: Expose the new specialized action without replacing legacy USD behavior or creating an ambiguous choice for unrelated products.

**Independent Test**: Inspect compatible actions for camera/USD, non-camera/USD, and non-USD representations and compare the new action order with generic USD loaders.

- [ ] T013 [US4] Verify compatibility attributes and labels/order for `UsdCameraLoaderV2`, legacy `UsdCameraLoader`, `GeoImportLoader`, and `GeoReferenceLoader` against `specs/001-nuke-usd-camera-loader/contracts/loader-contract.md`; adjust only the new class if required in `client/ayon_nuke/plugins/load/load_camera_usd.py`

## Phase 7: User Story 5 — Remove a USD camera container (P3)

**Goal**: Complete the V2 loader lifecycle without orphan nodes or metadata.

**Independent Test**: Load and remove a V2 container, then verify the node is deleted and existing unrelated nodes remain.

- [ ] T014 [US5] Verify V2 removal uses the container node object and does not name-lookup or delete unrelated nodes in `client/ayon_nuke/plugins/load/load_camera_usd.py`

## Phase 8: Settings and cross-cutting validation

- [ ] T015 [P] Add exact `UsdCameraLoaderV2: LoaderEnabledModel` model field and `enabled=True` default to `server/settings/loader_plugins.py`; verify `server/settings/main.py` composition requires no change and `server/settings/conversion.py` requires no migration
- [ ] T016 [P] Update implementation/design documentation with final class name, before/after contracts, settings key, and manual evidence requirements in `specs/001-nuke-usd-camera-loader/`
- [ ] T017 Run `ruff check .` from the addon root and fix only feature-related diagnostics outside `client/ayon_nuke/vendor/`
- [ ] T018 Run `ruff format --check .` from the addon root and apply repository formatting only to changed non-vendor files
- [ ] T019 Run `python create_package.py --skip-zip` from the addon root and verify package generation succeeds without a Nuke interpreter
- [ ] T020 Perform the manual Nuke + AYON create → publish → load V2 → edit → update → switch → remove round trip, including missing-file/no-camera/runtime-unavailable rollback cases, per `specs/001-nuke-usd-camera-loader/quickstart.md`

## Dependencies and execution order

- T001–T005 are foundational and must complete before loader implementation.
- T006–T008 deliver the MVP load story.
- T009–T011 depend on T006–T008 and deliver update/switch/remove lifecycle behaviour.
- T012–T014 depend on the V2 lifecycle implementation.
- T015 can run in parallel with T006–T014 because it edits only server settings; T016 can run in parallel after the plan is accepted.
- T017–T019 follow implementation; T020 requires a compatible Nuke + AYON environment and all code tasks.

### Parallel opportunities

- T002 and T016 can proceed in parallel with independent review/documentation work.
- T015 is parallel with client implementation because it touches only `server/settings/loader_plugins.py`.
- After T008, T009 and T015 can proceed in parallel; after T011, T013 and T014 can proceed in parallel.

## Implementation strategy

1. Preserve the legacy loader first and establish safe USD/runtime helpers.
2. Deliver the specialized V2 load path as the MVP.
3. Add transactional update and lifecycle operations.
4. Wire settings and validate filtering/order contracts.
5. Run the automated ladder, then obtain human Nuke evidence; do not claim host validation from a normal interpreter.
