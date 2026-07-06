def get_read_node_file_path(representation):
    """
    Get the file path for the Read node from the representation.

    Handles single frame renders correctly by not including frame padding
    when the frame range is a single frame.
    """
    # Get frame range from representation
    frame_start = representation.get("frameStart")
    frame_end = representation.get("frameEnd")
    padding = representation.get("padding", 4)

    # Use the first file in the representation's files list
    files = representation.get("files", [])
    if not files:
        return None

    # The first file should be representative
    file_name = files[0]
    # Assume file name is like 'render.0001.exr' or 'render.exr'
    # Determine if it's a sequence by checking if frameStart and frameEnd differ
    if frame_start is not None and frame_end is not None and frame_start == frame_end:
        # Single frame: remove padding pattern from file name
        # Strip padded version: find the padded part and remove it
        # For simplicity, if the file has a pattern like '.0001.', replace with ''
        import re
        # Construct the padded pattern: e.g., '.%04d.' -> convert to regex
        # Actually, better to rely on the fact that single frame files have no padding
        # The representation may still have padding info, but we should not enforce it
        # Instead, we can set the file path directly without frame specification
        # Nuke's Read node will treat the file as a single frame if no %0Xd pattern
        # So we need to return the file path as-is (no hashed pattern)
        return file_name
    else:
        # Sequence: Needs to be converted to Nuke's frame pattern
        # Typical: 'render.0001.exr' -> 'render.%04d.exr'
        import re
        # Remove the frame number part
        # This assumes the pattern is something like '.0001.' in the middle
        # For simplicity, we can use the frameStart and padding to build pattern
        # But the actual file name might differ; we need proper logic
        # Here we keep a simple placeholder
        # For production, use proper AYON/Nuke utilities
        head, tail = file_name.rsplit('.', 1)
        # Remove the last numeric part before the extension
        # This is a naive approach
        parts = head.rsplit('.', 1)
        if len(parts) == 2 and parts[1].isdigit():
            base = parts[0]
            pattern = f"{base}.%0{padding}d.{tail}"
            return pattern
        else:
            # No numeric part found, return as is
            return file_name
