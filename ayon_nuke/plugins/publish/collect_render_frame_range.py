import nuke
from ayon_core.pipeline.publish import PublishValidationError
from ayon_nuke.api import plugin


class CollectRenderFrameRange(plugin.NukePublishInstancePlugin):
    """Collect frame range for render products, handling custom frame ranges."""

    order = plugin.NukePublishInstancePlugin.order - 0.05
    families = ["render"]
    label = "Collect Render Frame Range"

    def process(self, instance):
        # Get script root frame range
        root = nuke.root()
        script_first = int(root["first_frame"].value())
        script_last = int(root["last_frame"].value())

        # Check if instance has custom frame range enabled
        custom_range = instance.data.get("customFrameRange", False)
        if custom_range:
            # If custom frame range is set but no explicit values, inherit script range
            if "frameStart" not in instance.data or "frameEnd" not in instance.data:
                instance.data["frameStart"] = script_first
                instance.data["frameEnd"] = script_last
            # Ensure the frameStart and frameEnd are integers
            instance.data["frameStart"] = int(instance.data.get("frameStart", script_first))
            instance.data["frameEnd"] = int(instance.data.get("frameEnd", script_last))
        else:
            # No custom range, use script range
            instance.data["frameStart"] = script_first
            instance.data["frameEnd"] = script_last

        # Validate frame range
        if instance.data["frameStart"] > instance.data["frameEnd"]:
            raise PublishValidationError(
                "Frame start is greater than frame end: {} > {}".format(
                    instance.data["frameStart"],
                    instance.data["frameEnd"]
                )
            )

        self.log.debug(
            "Render frame range: {} - {}".format(
                instance.data["frameStart"],
                instance.data["frameEnd"]
            )
        )
