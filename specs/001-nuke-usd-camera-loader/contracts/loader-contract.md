# Loader Contract: USD Camera Loader V2

## Discovery and compatibility

| Contract | Legacy value | New value / action |
| --- | --- | --- |
| Loader identifier | `UsdCameraLoader` | Add `UsdCameraLoaderV2` |
| Product base type | `{ "*" }` | `{ "camera" }` |
| Product types | wildcard | same as new base types |
| Representation names | `{ "*" }` | `{ "usd" }` |
| Extensions | `usd/usda/usdc` | `usd/usda/usdc` |
| Loader order | 2 | 1 |
| Settings key | none | `nuke.load.UsdCameraLoaderV2` |

Legacy values remain to preserve saved containers and non-camera USD products. The new class is intentionally a distinct Loader action and label.

## Lifecycle interface

The new class implements the ayon-core LoaderPlugin lifecycle:

- `load(context, name, namespace, data) -> nuke.Node`
- `update(container, context) -> nuke.Node`
- `switch(container, context) -> nuke.Node`
- `remove(container) -> None`

All container persistence uses `ayon_nuke.api.containerise`, `parse_container` and `update_container`; no parallel metadata format is permitted.

## Failure contract

Missing USD runtime, unsupported Nuke class/knob, missing file, unreadable USD stage or no camera prim must produce a clear loader error. Load must leave no partial node. Update must restore the previous file, frame rate, prim path, colour and container metadata when failure occurs after mutation begins.
