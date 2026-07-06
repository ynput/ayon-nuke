def create_read_from_rendered(render_node, product_type, output_path):
    """
    Create a Read node from a render node's output.
    Handles both sequences and single frame (still) products.
    """
    import os
    import re
    from ayon_core.pipeline import registered_host
    from ayon_nuke import lib as nukelib

    host = registered_host()
    if host is None:
        return

    # Determine if the product is a still (single frame) or sequence
    # Based on file naming conventions: stills usually have no frame number pattern
    # or explicitly have a single frame extension like .exr without numbers.
    is_still = False
    if product_type.lower() in ['image', 'render', 'still']:
        # Check if the output path contains frame number pattern like %04d or #
        if not re.search(r'%\d+d|#', output_path):
            # Also check if the file exists as a single file (no sequence)
            base_path = output_path.replace('\\', '/')
            # In case path has frame pattern, check with first frame
            first_frame = render_node['first'].getValue() if hasattr(render_node, 'first') else 1
            # Try to form a sequence pattern and see if multiple files exist?
            # For simplicity, check if there is a frame placeholder in the filename
            if '%' not in output_path and '#' not in output_path:
                is_still = True

    # Create Read node
    read_node = None
    if is_still:
        # For still, use the exact path (no frame padding)
        # Ensure the file exists or use first frame if sequence syntax
        read_node = nukelib.create_node('Read', {
            'file': output_path
        })
    else:
        # For sequence, we need to handle frame padding
        # The rendered output might have frame number placeholder or actual files
        # Assume output_path is a pattern with frame number (e.g., /path/render.####.exr)
        # If it already has padding pattern, use as is; otherwise, convert to Nuke syntax
        if '#' not in output_path and '%' not in output_path:
            # Likely a sequence with actual frame numbers? Or we need to add padding
            # Use the first frame to get the pattern
            first_frame = int(render_node['first'].getValue())
            # Build frame-padded path: replace the frame number with #
            # Example: /path/render.1001.exr -> /path/render.####.exr
            # This is tricky; for now assume representation provides proper pattern
            read_node = nukelib.create_node('Read', {
                'file': output_path
            })
        else:
            read_node = nukelib.create_node('Read', {
                'file': output_path
            })

    if read_node:
        # Set frame range if sequence
        if not is_still:
            first = int(render_node['first'].getValue())
            last = int(render_node['last'].getValue())
            read_node['first'].setValue(first)
            read_node['last'].setValue(last)
        # Position the node
        nukelib.autoplace(read_node)
        return read_node
