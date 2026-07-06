import nuke
import re

def create_read_node_from_write_node_fixed(write_node):
    """
    Create a Read node from a Write node's rendered output.
    Handles single-frame (still) products by avoiding frame padding.
    """
    file_path = write_node['file'].value()
    first_frame = int(write_node['first'].value())
    last_frame = int(write_node['last'].value())
    
    if first_frame == last_frame:
        # Single frame case: reconstruct the exact filename
        frame = first_frame
        # Detect pattern: %0Xd or # repetitions
        pattern = None
        match = re.search(r'%0?(\d+)d', file_path)
        if match:
            width = int(match.group(1))
            pattern = match.group()
        else:
            hash_match = re.search(r'#+', file_path)
            if hash_match:
                width = len(hash_match.group())
                pattern = hash_match.group()
        if pattern:
            frame_str = str(frame).zfill(width)
            actual_path = file_path.replace(pattern, frame_str, 1)
        else:
            # No pattern, assume file is a still (e.g., .exr without frame number)
            actual_path = file_path
        
        read_node = nuke.nodes.Read(file=actual_path)
        read_node['first'].setValue(frame)
        read_node['last'].setValue(frame)
    else:
        # Sequence: use original path with padding (existing behavior)
        read_node = nuke.nodes.Read(file=file_path)
        read_node['first'].setValue(first_frame)
        read_node['last'].setValue(last_frame)
    
    return read_node
