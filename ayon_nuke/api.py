import re
from ayon_core.lib import Logger
from ayon_core.pipeline import get_current_project
from ayon_nuke import utils

log = Logger.get_logger(__name__)

def create_read_from_write(write_node, context):
    """Create a Read node from a Write node's rendered output."""
    import nuke

    # Get the file path from the write node
    file_path = write_node['file'].getValue()
    
    # Check if it's a single frame (no padding pattern)
    # If the file path contains '%' or '#', it has padding
    if '%' in file_path or '#' in file_path:
        # Has padding, parse as sequence
        first_frame = write_node['first'].getValue()
        last_frame = write_node['last'].getValue()
        # Determine padding
        padding_match = re.search(r'%0?(\\d+)d', file_path)
        if padding_match:
            padding = int(padding_match.group(1))
        else:
            # Assume 4 digits for hash pattern
            padding = 4
        # Create read node with proper frame range
        read_node = nuke.createNode('Read')
        read_node['file'].setValue(file_path)
        read_node['first'].setValue(first_frame)
        read_node['last'].setValue(last_frame)
        # Set the frame range to the exact range
        read_node['origfirst'].setValue(first_frame)
        read_node['origlast'].setValue(last_frame)
    else:
        # Single frame, no padding
        read_node = nuke.createNode('Read')
        read_node['file'].setValue(file_path)
        # For single frame, set first and last to the same, but we don't know frame number
        # Try to extract frame number from filename (e.g., image.1001.exr)
        frame_match = re.search(r'\\.(\\d+)\\.', file_path)
        if frame_match:
            frame = int(frame_match.group(1))
            read_node['first'].setValue(frame)
            read_node['last'].setValue(frame)
            read_node['origfirst'].setValue(frame)
            read_node['origlast'].setValue(frame)
        else:
            # Assume first frame of write node
            first_frame = write_node['first'].getValue()
            read_node['first'].setValue(first_frame)
            read_node['last'].setValue(first_frame)
            read_node['origfirst'].setValue(first_frame)
            read_node['origlast'].setValue(first_frame)

    return read_node
