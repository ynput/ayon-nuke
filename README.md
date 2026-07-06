# Fix for YN-0692: Single frame read from rendered button padding issue

## Problem
When using the "Read Rendered" button on a Write node for image still products (single frame), Nuke reports a padding issue because the file path is constructed with an invisible padding pattern (e.g., `%04d`) even though the product is a single frame.

## Solution
The `fix_representation_path` function in `ayon_nuke/tools/read_rendered.py` now checks if the representation is a single frame (still) by comparing `frameStart` and `frameEnd`. If they are equal, it uses the actual file path from the representation's files list instead of a padded pattern.

## Usage
Replace the existing `read_rendered.py` in your AYON Nuke installation with the provided version. The fix is backward-compatible; sequences will continue to work as before.

## Notes
- The `get_representation_for_write_node` function is a placeholder and must be implemented to retrieve the correct representation from the AYON database.
- Ensure that the representation's `files` list contains the correct path for single frames.