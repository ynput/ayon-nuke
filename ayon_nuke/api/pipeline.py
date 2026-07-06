# Patch for YN-0692: Single frame read from rendered button missing padding issue
# Override the get_read_node_path or similar function

def get_read_node_path(product_data, context):
    """Get file path for read node, handling single-frame sequences."""
    import os
    path = product_data.get('path')
    if not path:
        return None
    # If the sequence has only one frame, use the file directly
    # Assume product_data has 'frame_start', 'frame_end', or 'frames'
    frame_start = product_data.get('frame_start')
    frame_end = product_data.get('frame_end')
    if frame_start is not None and frame_end is not None:
        if frame_start == frame_end:
            # Single frame: remove padding pattern from path
            # Example: /path/to/file.%04d.exr -> /path/to/file.0001.exr
            # or directly use the path as is if it's not a sequence pattern
            # Usually the path has '%0Xd' pattern
            import re
            match = re.search(r'%0\d+d', path)
            if match:
                padding = int(match.group()[2:-1])  # e.g., 4 from %04d
                # Replace with actual frame number
                path = path.replace(match.group(), str(frame_start).zfill(padding))
                # Also ensure the path ends with the frame number
                # But the pattern might be elsewhere
            # Alternative: use the first file in the list
            # If product_data has 'files' list, use first file
            files = product_data.get('files', [])
            if files:
                # Get the directory and base name
                directory = os.path.dirname(path)
                # But path may already have pattern; better to use files list
                path = os.path.join(directory, files[0])
            return path
    # For sequences, return the path as is (with padding pattern)
    return path

# Then you would replace the original function in the pipeline module.
