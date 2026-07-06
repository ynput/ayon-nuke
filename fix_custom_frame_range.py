import nuke

def set_render_frame_range(product_node, custom_frame_range=None):
    """
    Ensure render products inherit script root frame range when custom range is not provided.
    """
    if custom_frame_range is None:
        # Inherit from script root
        root = nuke.root()
        first_frame = int(root['first_frame'].value())
        last_frame = int(root['last_frame'].value())
        product_node['first'].setValue(first_frame)
        product_node['last'].setValue(last_frame)
    else:
        # Validate custom range is properly set (not 1-1 unexpectedly)
        first, last = custom_frame_range
        if first == 1 and last == 1:
            # Suspect fallback, use script root instead
            root = nuke.root()
            first = int(root['first_frame'].value())
            last = int(root['last_frame'].value())
        product_node['first'].setValue(first)
        product_node['last'].setValue(last)
