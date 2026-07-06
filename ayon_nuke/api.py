# Fixed version of create_read_from_write function

def create_read_from_write(write_node):
    """Create a Read node from a Write node, handling single frames correctly."""
    import nuke
    import os
    
    # Get the file path from the Write node
    file_path = nuke.filename(write_node)
    if not file_path:
        nuke.message("Write node has no file path set.")
        return None
    
    # Get the frame range
    first_frame = write_node['first'].value()
    last_frame = write_node['last'].value()
    
    # Determine if it's a single frame (still image)
    is_single_frame = (first_frame == last_frame) or (write_node['use_limit'].value() and first_frame == last_frame)
    
    # For single frame, we need to replace any padding pattern with the actual frame number
    if is_single_frame:
        # Example: /path/to/render.####.exr -> /path/to/render.0001.exr
        # We need to find the padding pattern and replace with the first frame
        import re
        # Common padding patterns: #, %0Xd, %d, etc.
        # Nuke uses # for padding, but also can use printf style
        # Let's handle # and %d patterns
        frame_number = int(first_frame)
        padded_frame = str(frame_number).zfill(4)  # Default padding 4 digits
        # Replace #### with padded frame
        file_path_fixed = re.sub(r'#+', lambda m: str(frame_number).zfill(len(m.group())), file_path)
        # Also handle %0Xd patterns
        def replace_percent(match):
            pattern = match.group()
            if '%' in pattern and 'd' in pattern:
                # Extract width
                width_match = re.search(r'%0?(\d+)d', pattern)
                if width_match:
                    width = int(width_match.group(1))
                    return str(frame_number).zfill(width)
                else:
                    return str(frame_number)
            return pattern
        file_path_fixed = re.sub(r'%\d*d', replace_percent, file_path_fixed)
        # Also handle %d directly
        if '%d' in file_path_fixed:
            file_path_fixed = file_path_fixed.replace('%d', str(frame_number))
        # Ensure it's not a sequence pattern anymore
        # Now create the Read node
        read_node = nuke.nodes.Read(file=file_path_fixed)
        # Set frame range to single frame
        read_node['first'].setValue(first_frame)
        read_node['last'].setValue(first_frame)
        read_node['origfirst'].setValue(first_frame)
        read_node['origlast'].setValue(first_frame)
    else:
        # For sequences, keep existing behavior
        read_node = nuke.nodes.Read(file=file_path)
        read_node['first'].setValue(first_frame)
        read_node['last'].setValue(last_frame)
        read_node['origfirst'].setValue(first_frame)
        read_node['origlast'].setValue(last_frame)
    
    return read_node
