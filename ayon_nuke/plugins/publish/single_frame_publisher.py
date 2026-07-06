import pyblish.api
from ayon_core.pipeline.publish import KnownPublishError
from ayon_nuke.api import plugin

class SingleFramePublisher(plugin.NukePublishInstance):
    """Publish single frame with frame token resolved."""

    order = pyblish.api.CollectorOrder + 0.4
    label = "Single Frame Publisher"
    families = ["render"]
    match = pyblish.api.Exact

    def process(self, instance):
        # Check if this is a single frame instance
        creator_identifier = instance.data.get("creator_identifier")
        if creator_identifier != "io.ayon.creators.nuke.singleframe":
            return

        # Get the frame number from the instance
        frame_start = instance.data.get("frameStart")
        frame_end = instance.data.get("frameEnd")
        if frame_start is None or frame_end is None:
            raise KnownPublishError("Frame range not defined.")
        if frame_start != frame_end:
            raise KnownPublishError("Single frame must have identical start and end frame.")

        frame = int(frame_start)

        # Resolve variant token
        variant = instance.data.get("variant", "")
        if "{frame}" in variant:
            variant = variant.replace("{frame}", str(frame))
            instance.data["variant"] = variant
            self.log.debug(f"Resolved variant to: {variant}")

        # Also update any other fields that might use frame token (like product name)
        product_name = instance.data.get("productName", "")
        if "{frame}" in product_name:
            product_name = product_name.replace("{frame}", str(frame))
            instance.data["productName"] = product_name

        self.log.info(f"Single frame published with variant: {variant}")
