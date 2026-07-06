import nuke
from ayon_nuke.api import plugin
from ayon_nuke.api.plugin import NukeCreator

class CollectNukeInstances(NukeCreator):
    """Collect Nuke instances."""

    def process(self, instance):
        # ... existing code ...

        # Fix for YN-0694: Render product custom frame range should inherit script root range
        if instance.data.get('productType') == 'render':
            custom_frame_range = instance.data.get('customFrameRange', False)
            if custom_frame_range:
                # Ensure frameStart and frameEnd default to script root if not set
                if instance.data.get('frameStart') is None or instance.data.get('frameEnd') is None:
                    root = nuke.Root()
                    start = root['first_frame'].value()
                    end = root['last_frame'].value()
                    instance.data['frameStart'] = start
                    instance.data['frameEnd'] = end
        # ... rest of process ...
