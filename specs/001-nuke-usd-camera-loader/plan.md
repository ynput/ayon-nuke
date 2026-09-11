# Implementation Plan: Nuke USD Camera Loader with Container Update

**Branch**: `sdd_nuke_camera_usd_test` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

## Summary

Add a new, separately identified `UsdCameraLoaderV2` alongside the existing `UsdCameraLoader`. The legacy loader remains unchanged so saved containers continue to resolve. The new loader specializes the published camera/USD contract, creates a USD-capable versioned Camera node, resolves and records a camera prim, and updates the same node in place with transactional validation and AYON container metadata updates. Add the corresponding exact-class settings entry and make the new loader's action order deterministic.

## Technical Context

**Language/Version**: Python 3.9+ addon runtime; packaging validated with Python 3.11+.

**Primary Dependencies**: Nuke Python API, USD `pxr.Usd` / `pxr.UsdGeom` supplied by a USD-capable Nuke installation, ayon-core LoaderPlugin, ayon_api, and existing `ayon_nuke.api` container and selection helpers.

**Storage**: Nuke node knobs and existing AYON container schema `ayon:container-3.0`; no new persistent store or metadata format.

**Testing**: No checked-in test suite and no new test framework. Run `ruff check .`, `ruff format --check .`, `python create_package.py --skip-zip`; validate host behaviour manually in Nuke + AYON.

**Target Platform**: Nuke 15+ with USD import and a Camera4-capable camera node for the new path; fail clearly when the required runtime is unavailable.

**Project Type**: AYON host-integration addon. Launcher-safe registration remains separate from host/API-dependent loader modules.

**Performance Goals**: One USD-stage open and deterministic prim traversal per load/update; no additional network/database work beyond existing representation resolution and latest-version colour query.

**Constraints**: Preserve node identity, name, position, connections and user knobs on update. Preserve the existing `UsdCameraLoader` class, identifier, wildcard compatibility and order. Do not touch vendor code or add GUI/menu/startup work. Use forward-slash paths at the Nuke boundary.

**Scale/Scope**: One new loader class, one loader settings model entry/default, and targeted changes to the existing USD loader module; no publisher, extractor, server API, creator or Pyblish changes.

## Constitution Check

*GATE: Must pass before Phase 0 research and after Phase 1 design.*

- **Article 1 — Addon anatomy**: PASS. Changes remain in existing client load, server settings, and feature documentation paths. No new top-level directory.
- **Article 2 — Pipeline contracts**: PASS with explicit additive change. Existing `UsdCameraLoader` identifier, wildcard filters and order remain unchanged. New persisted loader identifier is `UsdCameraLoaderV2`; its filter is camera/USD and its action order is explicitly set to 1.
- **Article 3 — Settings contract**: PASS. Add exact key `UsdCameraLoaderV2` and default `enabled=True` in `server/settings/loader_plugins.py`. No field rename, so no conversion is needed; `main.py` already composes the load model/defaults.
- **Article 4 — Compatibility imports**: PASS. Existing ayon-core loader API and Nuke-version handling are retained.
- **Article 5/6 — Ruff/vendor**: PASS. Follow repository `ruff.toml`; do not change `client/ayon_nuke/vendor/`.
- **Article 7 — Runtime boundary**: PASS. Nuke and USD imports are confined to the host plugin module. Guard USD availability so discovery does not crash; do not alter launcher-safe `addon.py` or headless startup paths.
- **Article 8 — Verification ladder**: PASS. Use lint, format, package build, then human Nuke validation; no tests are added.

## Design Artifacts

- [research.md](research.md) — decisions and evidence.
- [data-model.md](data-model.md) — representation, node, container and USD prim state.
- [contracts/loader-contract.md](contracts/loader-contract.md) — loader/plugin contract and before/after pipeline values.
- [quickstart.md](quickstart.md) — automated gates and manual Nuke + AYON validation.

## Project Structure

```text
client/ayon_nuke/plugins/load/load_camera_usd.py
  Existing UsdCameraLoader (preserve)
  New UsdCameraLoaderV2 (additive specialized loader)
server/settings/loader_plugins.py
  UsdCameraLoaderV2 model field and default
server/settings/main.py
  No change expected: existing load model composition is sufficient
server/settings/conversion.py
  No change expected: additive settings only
```

**Structure Decision**: Keep the existing host-addon layout. Implement the new class in the existing USD loader module unless discovery/runtime review shows a separate module is required; no new top-level directory or vendor change is allowed.

## Implementation Sequencing

1. Harden optional USD import and add reusable stage/prim validation helpers without changing legacy loader behaviour.
2. Add `UsdCameraLoaderV2` with specialized compatibility metadata, distinct label/settings key, and explicit order.
3. Implement load/update/switch/remove using existing `containerise`, `parse_container` and `update_container`; validate new files before mutating nodes and restore captured knob/container values on failure.
4. Wire server settings and verify class-name alignment.
5. Run automated gates and perform the manual Nuke + AYON round trip.

## Complexity Tracking

No constitution violations. The second loader identifier is an intentional additive Article 2 contract required by Q1=B; keeping the legacy loader is safer than migrating saved Nuke containers.
