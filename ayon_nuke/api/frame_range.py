import nuke

def apply_custom_frame_range(instance_data):
    """Apply custom frame range from instance data to the script root.

    This function is called for render products with custom frame range.
    It ensures the root first and last frame match the custom range.
    """
    if not instance_data:
        return

    # Retrieve custom frame range from instance attributes
    custom_first_frame = instance_data.get("customFirstFrame")
    custom_last_frame = instance_data.get("customLastFrame")

    if custom_first_frame is None or custom_last_frame is None:
        # No custom range defined, do nothing
        return

    # Validate values
    try:
        first = int(custom_first_frame)
        last = int(custom_last_frame)
    except (ValueError, TypeError):
        return

    if first > last:
        first, last = last, first

    # Set root frame range
    root = nuke.root()
    root["first_frame"].setValue(first)
    root["last_frame"].setValue(last)
