from ayon_core.pipeline import publish
import pyblish.api

class ResolveFrameVariant(pyblish.api.InstancePlugin):
    """Resolve {frame} token in variant for single frame renders."""
    order = pyblish.api.CollectorOrder + 0.5
    label = "Resolve Frame Variant"
    families = ["render"]

    def process(self, instance):
        variant = instance.data.get("variant", "")
        if "{frame}" not in variant:
            return
        # Only resolve for single frame instances
        frame_start = instance.data.get("frameStart")
        frame_end = instance.data.get("frameEnd")
        if frame_start is not None and frame_start == frame_end:
            instance.data["variant"] = variant.replace(
                "{frame}", str(int(frame_start))
            )