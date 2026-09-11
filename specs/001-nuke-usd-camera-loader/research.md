# Research: Nuke USD Camera Loader with Container Update

## Decision 1 — Add a separate class, preserve the legacy class

- **Decision**: Implement `UsdCameraLoaderV2` as a distinct LoaderPlugin while retaining `UsdCameraLoader` unchanged for old containers.
- **Rationale**: `containerise` stores `loader = self.__class__.__name__`; ayon-core resolves persisted loaders by class name. Renaming/replacing the old class would orphan existing Nuke containers. The user selected Q1=B.
- **Alternatives**: Refine the old class in place (Q1=A) was rejected; retiring the old class requires a saved-scene migration that this addon does not have.
- **Evidence**: `client/ayon_nuke/api/pipeline.py`, ayon-core `get_loader_identifier`, and existing update-capable loaders.

## Decision 2 — Split compatibility by published camera contract

- **Decision**: New class uses `product_base_types = {"camera"}`, `product_types = product_base_types`, `representations = {"usd"}`, and extensions `usd/usda/usdc`. Legacy class keeps wildcard product and representation filters and all three extensions.
- **Alternative rejected**: Both wildcard would create indistinguishable choices; narrowing the legacy class would break existing scope.

## Decision 3 — Explicit action order

- **Decision**: New class order is 1; legacy `UsdCameraLoader` remains order 2; `GeoImportLoader` remains order 2 and `GeoReferenceLoader` remains 3.
- **Rationale**: The new specialized camera loader is shown before generic USD import choices without modifying the legacy action contract. The legacy/GeoImport tie is pre-existing and outside the additive class change.
- **Alternative rejected**: Changing legacy order would alter existing UI ordering unnecessarily; using order 2 creates a new tie.

## Decision 4 — Camera node and version compatibility

- **Decision**: Use a USD-import-capable Camera-family node, preferring the runtime-supported current version (Camera4 in current Nuke), and use existing Camera-family matching logic rather than hard-coding a generic Camera class.
- **Rationale**: `load_camera.py` handles Camera3/Camera2 versions and `api/plugin.py` matches `Camera` plus numeric suffixes. USD knobs such as `import_enabled` and `import_prim_path` are runtime contracts and must be checked before use.
- **Alternative rejected**: Always creating Camera4 fails on older builds; Camera2 lacks the USD import path.

## Decision 5 — Validate before mutating, then update in place

- **Decision**: Resolve the representation path, open the USD stage and resolve a valid prim path before changing the existing node. Capture file/frame-rate/import-path/tile colour and parsed container data; if mutation/validation fails, restore captured knob values and container data. On success, set file, frame rate and prim path, force validation/reload, colour the node, then call `update_container` with changed metadata.
- **Rationale**: Node identity and user knobs must survive; delete/recreate violates FR-007. Existing loaders demonstrate update helpers, while the known metadata-growth bug requires no duplicate writes.
- **Alternatives rejected**: Recreate the node, or mutate first and leave a broken container on error.

## Decision 6 — USD runtime boundary

- **Decision**: Guard `pxr` import and provide an actionable loader error when USD is unavailable. Keep Nuke-dependent code in the plugin module; do not import it from `addon.py` or GUI startup paths.
- **Rationale**: Article 7 requires launcher-safe addon registration and host-only API code. An unguarded module import makes discovery drop the loader when `pxr` is unavailable.

## Decision 7 — Settings

- **Decision**: Add `UsdCameraLoaderV2: LoaderEnabledModel` and `enabled=True` to `server/settings/loader_plugins.py`; no `main.py` or conversion change.
- **Rationale**: ayon-core `LoaderPlugin.apply_settings` looks up the exact class name under `project_settings["nuke"]["load"]`; existing top-level composition already consumes the defaults dict. This is additive, so no stored override migration is required.
