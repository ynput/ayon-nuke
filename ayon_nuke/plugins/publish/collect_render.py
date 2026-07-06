import nuke


def set_frame_range_to_root(instance):
    """Ensure that render product instances use root frame range when custom range is not explicitly set."""
    root = nuke.root()
    root_first = root['first_frame'].value()
    root_last = root['last_frame'].value()
    
    custom_first = instance.data.get('frameStart')
    custom_last = instance.data.get('frameEnd')
    
    # If custom range is not set or set to 0 or empty string, use root range
    if not custom_first or custom_first == 0 or custom_first == '':
        instance.data['frameStart'] = int(root_first)
    else:
        try:
            instance.data['frameStart'] = int(custom_first)
        except ValueError:
            instance.data['frameStart'] = int(root_first)
    
    if not custom_last or custom_last == 0 or custom_last == '':
        instance.data['frameEnd'] = int(root_last)
    else:
        try:
            instance.data['frameEnd'] = int(custom_last)
        except ValueError:
            instance.data['frameEnd'] = int(root_last)


def collect_render(instances):
    """Collect render instances and ensure correct frame range."""
    for instance in instances:
        if instance.data.get('productType') == 'render':
            set_frame_range_to_root(instance)
    # original collection logic continues...
    # ...
