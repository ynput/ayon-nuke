def get_valid_frame_range(product, script_root):
    """
    Return the frame range to use for a render product.
    If the product has a custom frame range set, use it;
    otherwise, fall back to the script root's first and last frame.
    """
    custom_first = product.get('customFrameRangeStart')
    custom_last = product.get('customFrameRangeEnd')
    if custom_first is not None and custom_last is not None:
        try:
            first = int(custom_first)
            last = int(custom_last)
            if first <= last:
                return first, last
        except (ValueError, TypeError):
            pass
    # Fallback to script root
    root = script_root
    first = root['first_frame'].value()
    last = root['last_frame'].value()
    return first, last
