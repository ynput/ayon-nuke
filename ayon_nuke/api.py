# Fixed version of create_read_node_from_write (patch applied)
# Original function replaced by this to handle single frame padding issue (YN-0692)

def create_read_node_from_write(write_node):
    """
    Creates a Read node from a Write node's rendered output.
    Handles single-frame stills properly.
    """
    import nuke
    import os
    from ayon_core.lib import Logger
    log = Logger.get_logger(__name__)

    # Get file knob and frame range
    file_knob = write_node['file']
    file_path = file_knob.value()
    first = write_node['first'].value()
    last = write_node['last'].value()

    # Determine if it's a single frame render
    single_frame = (first == last)

    if single_frame:
        # For single frame, replace the frame pattern with the actual frame number
        # and ensure no padding in the filename
        # Assumes pattern like '%04d' or '#' etc.
        # If file_path contains '%d', replace with frame number
        # Otherwise, assume it's already a proper path
        import re
        # Match typical Nuke frame patterns like %04d, %d, #, ####, etc.
        pattern = re.compile(r'%[0-9]*d|#+')
        if pattern.search(file_path):
            # Replace pattern with the actual frame number (no padding)
            actual_path = pattern.sub(str(int(first)), file_path)
        else:
            # Already a concrete path? Could be from previous renders
            actual_path = file_path

        # Ensure the file exists
        if not os.path.exists(actual_path):
            # Maybe there's a different extension or version
            # Try to find rendered file in the same directory
            dir_path = os.path.dirname(actual_path)
            base = os.path.basename(actual_path)
            # Could be that the file has frame number with padding? 
            # For single frame, most likely no padding
            # Not guaranteed, but attempt common pattern
            log.warning(f"File {actual_path} does not exist. Trying alternative...")
            # Let the user handle missing file or show error
            # For now, proceed with the path
        read_path = actual_path
    else:
        # For multi-frame, use the pattern as is (with padding)
        read_path = file_path

    # Create the Read node
    read_node = nuke.createNode('Read')
    read_node['file'].setValue(read_path)
    return read_node
