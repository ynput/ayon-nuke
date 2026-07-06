import os
import nuke
from ayon_core.pipeline import get_current_project_name
from ayon_core.tools.utils import get_representation_path


def create_read_node_from_representation(representation, context=None):
    """Create a Read node from a render representation.

    Handles both sequences and single frames (stills).
    For stills, uses exact file path without frame padding.
    """
    path = get_representation_path(representation)
    if not path:
        raise ValueError("Representation path is empty")

    # Determine if it's a single frame
    frame_start = representation.get("frameStart")
    frame_end = representation.get("frameEnd")
    is_single_frame = (
        frame_start is not None
        and frame_end is not None
        and frame_start == frame_end
    )

    if is_single_frame:
        # For single frame, use exact file path (already includes frame number or is a still)
        file_path = path
        # Remove any existing frame padding if present (e.g., filename.%04d.ext)
        # But typically path is already resolved to the specific file
        read_node = nuke.createNode("Read")
        read_node["file"].setValue(file_path)
        read_node["origfirst"].setValue(1)
        read_node["first"].setValue(1)
        read_node["last"].setValue(1)
    else:
        # For sequence, use the pattern with padding
        # Ensure path ends with frame placeholder
        file_path = path
        read_node = nuke.createNode("Read")
        read_node["file"].setValue(file_path)
        if frame_start is not None and frame_end is not None:
            read_node["first"].setValue(frame_start)
            read_node["last"].setValue(frame_end)
            read_node["origfirst"].setValue(frame_start)

    # Set other metadata if available
    if context:
        project = context.get("project")
        if project:
            read_node["tile_color"].setValue(0x4f4f4fff)  # example color

    return read_node
