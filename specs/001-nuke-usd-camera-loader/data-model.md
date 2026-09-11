# Data Model: Nuke USD Camera Loader

## Representation context

- `project.name`: owning AYON project.
- `product.productBaseType`: `camera` for the new specialized loader.
- `representation.name`: `usd` for the new specialized loader.
- `representation.context.ext`: `usd`, `usda` or `usdc`.
- `version.attrib.fps`: optional frame rate; fallback is Nuke root fps.
- `version.attrib.frameStart/frameEnd/source`: optional imprint metadata.
- Resolved representation path is normalized to forward slashes before assigning to Nuke.

## Nuke camera node

- Native class: runtime USD-capable Camera-family version.
- Required runtime knobs: `file`, `frame_rate`, `import_enabled`, `import_prim_path`, `tile_color`; availability is validated rather than assumed.
- Identity fields: Nuke node object/name, position, input/output connections and all user knobs. Update retains these.
- USD prim path: valid `UsdGeom.Camera` path selected deterministically; a valid prior path is retained across update.

## AYON container

The existing helpers manage schema `ayon:container-3.0`. Required fields include `schema`, `id`, `name`, `namespace`, `loader`, `representation`, and `project_name`.

- New containers store `loader = "UsdCameraLoaderV2"`; old containers continue storing `UsdCameraLoader`.
- Update metadata replaces representation id, version, frame range, source and fps without duplicating keys.

## State transitions

1. **Unloaded → Loaded**: resolve file and camera prim, create node, imprint container.
2. **Loaded → Updated**: validate new file/prim, mutate same node, refresh metadata and colour.
3. **Loaded → Unchanged**: same representation update performs no destructive work.
4. **Loaded → Failed update**: restore previous node/container state; remain Loaded.
5. **Loaded → Removed**: delete the container node via existing remove convention.
