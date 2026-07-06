import pyblish.api
from ayon_core.pipeline import registered_host
from ayon_nuke.api import NukeHost

class CollectRenderSingleFrameVariant(pyblish.api.Collector):
    """Add frame token to variant for single frame renders."""
    order = pyblish.api.Collector.order + 0.1
    label = "Single Frame Variant"
    families = ["render"]

    def process(self, context):
        host = registered_host()
        if not isinstance(host, NukeHost):
            return

        for instance in context:
            product_type = instance.data.get("productType")
            if product_type != "render":
                continue
            # Check if it's a single frame render
            frame_start = instance.data.get("frameStart")
            frame_end = instance.data.get("frameEnd")
            if frame_start is None or frame_end is None:
                continue
            if frame_start == frame_end:
                frame = int(frame_start)
                # Add frame to instance data for token substitution
                instance.data["frame"] = frame
                # Optionally update variant if token present
                variant = instance.data.get("variant", "")
                if variant and "{frame}" in variant:
                    instance.data["variant"] = variant.replace("{frame}", str(frame))
