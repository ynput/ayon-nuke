import os
import re

from ayon_core.pipeline import KnownPublishError
from ayon_nuke.api import NukeHost


def get_read_node_paths(render_node):
    """Get file paths from a Write node for reading."""
    from ayon_nuke.api import imprint

    file_path = render_node['file'].value()
    frame_range = render_node['frame'].value()

    # Handle single frame cases
    if not frame_range:
        # If no frame range specified, it's a single frame
        yield file_path
        return

    # Parse frame range
    try:
        frames = parse_frame_range(frame_range)
    except Exception as e:
        raise KnownPublishError(f"Failed to parse frame range: {e}")

    # Check if sequence or single
    if len(frames) == 1:
        # Single frame - may have padding or not
        yield inject_frame_number(file_path, frames[0])
    else:
        # Sequence - multiple frames
        for frame in frames:
            yield inject_frame_number(file_path, frame)


def parse_frame_range(frame_range_str):
    """Parse Nuke frame range string into list of ints."""
    from ayon_nuke.api import NukeHost
    host = NukeHost()
    # Use Nuke's own parsing
    import nuke
    return nuke.FrameRange(frame_range_str).frames()


def inject_frame_number(file_path, frame):
    """Replace hash marks or # with actual frame number, handling padding."""
    if '#' in file_path:
        # Count hashes for padding
        padding = file_path.count('#')
        frame_str = str(frame).zfill(padding)
        return file_path.replace('#' * padding, frame_str)
    else:
        # No hash marks, assume single file without padding
        # Check if file exists at original path
        if os.path.exists(file_path):
            return file_path
        else:
            # Try to find a pattern
            dirname, basename = os.path.split(file_path)
            name, ext = os.path.splitext(basename)
            # Pattern: name.%04d.ext or name.ext
            pattern = re.compile(rf'^{re.escape(name)}\.(\d+){re.escape(ext)}$')
            for f in os.listdir(dirname):
                match = pattern.match(f)
                if match:
                    return os.path.join(dirname, f)
            # Fallback: return original
            return file_path