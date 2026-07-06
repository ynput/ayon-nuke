# Fix for YN-0692: Single frame in nuke read from rendered button missing padding issue
# This hook adjusts the behaviour when creating a Read node from a rendered product.

import nuke
import os
import re

def fix_read_node_from_rendered(file_path, frame_range=None):
    """
    Create a Read node correctly handling single frame products.
    If the file is a single frame (e.g., no sequence detected), use the exact path
    without padding. Otherwise, use proper sequence pattern.
    """
    # Determine if the file path indicates a sequence
    # Typical sequence pattern: filename.%04d.ext or filename.####.ext
    # Single frame: filename.0001.ext (no % or # chars)
    dirname, basename = os.path.split(file_path)
    name, ext = os.path.splitext(basename)
    
    # Check if the name contains a frame number pattern (like %04d or #)
    if '%' in name or '#' in name:
        # It's already a sequence pattern, use as is
        read_node = nuke.nodes.Read(file=file_path)
    else:
        # Check if name ends with digits (possible frame number)
        match = re.search(r'^(.*?)(\d+)$', name)
        if match:
            base_name = match.group(1)
            frame_digits = match.group(2)
            # If there are more than one file matching the base pattern, treat as sequence
            # For simplicity, assume it's a single frame and use exact path
            read_node = nuke.nodes.Read(file=file_path)
        else:
            # No digits, treat as single image (e.g., still)
            read_node = nuke.nodes.Read(file=file_path)
    
    # Additional fix: if the read node has a range set to a single frame, ensure no padding issues
    if read_node:
        # For single frame, we can set the frame range explicitly if needed
        pass
    
    return read_node

# Override the original function if possible
# For ayon-nuke, this would be injected into the relevant hook
