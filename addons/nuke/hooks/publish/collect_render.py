import nuke
from ayon_core.pipeline import publish


class CollectNukeRenderInstances(publish.Collector):
    """Collect render write nodes as publish instances."""

    order = publish.Collector.order
    label = "Collect Nuke Render Instances"

    def process(self, instance):
        super().process(instance)

        # Get the script root frame range
        root = nuke.root()
        root_first = int(root["first_frame"].value())
        root_last = int(root["last_frame"].value())

        # Ensure instance has frameStartHandle and frameEndHandle
        if "frameStartHandle" not in instance.data:
            instance.data["frameStartHandle"] = root_first
        if "frameEndHandle" not in instance.data:
            instance.data["frameEndHandle"] = root_last

        # If custom frame range is enabled but values are not set or invalid, fallback to root
        custom_frame_range = instance.data.get("customFrameRange", False)
        if custom_frame_range:
            custom_start = instance.data.get("frameStart")
            custom_end = instance.data.get("frameEnd")
            # Validate: if not set, or if start > end, or if they are 0/1-1 pattern, use root
            if custom_start is None or custom_end is None or custom_start > custom_end:
                instance.data["frameStart"] = root_first
                instance.data["frameEnd"] = root_last
            elif custom_start == 1 and custom_end == 1:
                # Possibly default 1-1 from unset custom range
                instance.data["frameStart"] = root_first
                instance.data["frameEnd"] = root_last
