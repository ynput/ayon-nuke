# Quickstart: Nuke USD Camera Loader V2

This guide is split between host-independent package checks and manual checks requiring a compatible Nuke + AYON environment. The repository has no tests and no test framework should be added.

## Automated gates

From the addon root:

```bash
ruff check .
ruff format --check .
python create_package.py --skip-zip
```

Expected: all commands exit successfully; packaging succeeds without importing Nuke in the packaging interpreter. Confirm no files under `client/ayon_nuke/vendor/` were modified.

## Manual prerequisites

- AYON server with this addon package installed.
- Nuke 15+ (or a build exposing the required USD-capable Camera node and USD Python API).
- A published camera product with base type `camera`, representation name `usd`, and a valid USD file containing at least one camera prim.
- A second version of the same product and optionally a different camera product for switch validation.

## Manual round trip

1. Open a Nuke script and confirm the AYON Loader lists the new specialized `Load USD Camera (V2)` action for the camera/USD representation. Confirm the legacy action remains available with its distinct label and the new action is ordered before generic USD import.
2. Load with `UsdCameraLoaderV2`. Record node object/name, position, input/output connections, frame rate, file and imported prim path. Confirm the node is listed in Scene Inventory and its container loader is `UsdCameraLoaderV2`.
3. Publish/register a newer version. In the script, rename the node, add a downstream connection, change a user knob and set a valid custom prim path.
4. Update the container through Scene Inventory. Confirm the same node remains with the same name, position, connections and user knob; confirm file, frame rate, prim path, representation id, version metadata and colour update.
5. Repeat the update ten times and inspect container metadata for one bounded set of keys, not repeated avalon knobs.
6. Switch to another version/product. Confirm it uses the same in-place path and does not create a duplicate node.
7. Remove the container and confirm the node and AYON metadata are gone.
8. Error paths: try a missing file, a USD file with no camera prim, an invalid prior prim path and a runtime without USD support. Confirm actionable errors, no partial load node, and rollback to the former working state on update.
9. Regression: load an existing abc/fbx camera and a non-camera USD product; confirm legacy and generic USD loaders continue to work.

## Evidence to record

For review, record Nuke version, node class, loader identifier, selected representation, prim path before/after, node identity comparison, and automated gate output.
