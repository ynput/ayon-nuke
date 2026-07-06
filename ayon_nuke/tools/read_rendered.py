import nuke
import os
import re
from ayon_core.pipeline import registered_host
from ayon_nuke.api import get_representation_path

def fix_representation_path(path, representation):
    """Return correct file path for Read node, handling single frame (still)."""
    context = representation.get('context', {})
    frame_start = context.get('frameStart')
    frame_end = context.get('frameEnd')
    files = representation.get('files', [])

    # Check if it's a single frame (still)
    if frame_start is not None and frame_end is not None and frame_start == frame_end:
        if files:
            # Use the exact path from the representation (no padding)
            file_path = files[0].get('path')
            if file_path:
                return file_path
        # Fallback: replace padding pattern with actual frame number
        frame = int(frame_start)
        pad_match = re.search(r'%0(\d+)d', path)
        if pad_match:
            pad = int(pad_match.group(1))
            framed = str(frame).zfill(pad)
            return path.replace(pad_match.group(0), framed)
    return path

def create_read_node_from_write(write_node):
    """Create a Read node from the selected Write node's rendered output."""
    # Get representation from Write node (simplified; actual implementation depends on AYON integration)
    representation = get_representation_for_write_node(write_node)
    if not representation:
        nuke.message("No representation found for Write node.")
        return

    # Get file path and fix for single frame
    path = get_representation_path(representation)
    path = fix_representation_path(path, representation)

    # Create Read node
    read_node = nuke.createNode("Read")
    read_node["file"].setValue(path)

    # Additional setup (e.g., colorspace, frame range) can be added here
    return read_node

def get_representation_for_write_node(write_node):
    """Placeholder: retrieve representation linked to the Write node.
    Actual implementation should query AYON database or context."""
    # This function would need to be implemented based on AYON-Nuke integration
    # For now, return a dummy representation for testing
    return {
        'context': {'frameStart': 1, 'frameEnd': 1},  # single frame example
        'files': [{'path': '/path/to/render/single_frame.exr'}]
    }
