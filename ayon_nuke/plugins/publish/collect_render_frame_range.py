import pyblish.api
from ayon_core.lib import BoolDef, UIDef
from ayon_nuke.api import plugin


class CollectRenderFrameRange(pyblish.api.Collector):
    """Collect frame range for render products, inheriting script root if custom range not set."""

    order = pyblish.api.CollectorOrder - 0.1
    hosts = ["nuke"]
    label = "Collect Render Frame Range"

    def process(self, context):
        import nuke

        # Get script root frame range
        root_first = int(nuke.root()["first_frame"].getValue())
        root_last = int(nuke.root()["last_frame"].getValue())

        for instance in context:
            # Check if instance is a render product
            product_type = instance.data.get("productType")
            if product_type != "render":
                continue

            # Get custom frame range settings
            creator_attributes = instance.data.get("creator_attributes", {})
            frame_start = instance.data.get("frameStart")
            frame_end = instance.data.get("frameEnd")

            # If custom range is not defined or defaults to 1-1, inherit script root
            if (frame_start is None or frame_start == 1) and (frame_end is None or frame_end == 1):
                # Check if the user has explicitly set a custom range
                custom_range_enabled = creator_attributes.get("customFrameRange", False)
                if not custom_range_enabled:
                    # Inherit from script root
                    instance.data["frameStart"] = root_first
                    instance.data["frameEnd"] = root_last
                else:
                    # If custom range is enabled but not set, default to script root
                    if frame_start is None or frame_start == 1:
                        instance.data["frameStart"] = root_first
                    if frame_end is None or frame_end == 1:
                        instance.data["frameEnd"] = root_last
            else:
                # Custom range already set, keep as is
                pass

            self.log.debug(f"Instance {instance.data['name']}: frameStart={instance.data.get('frameStart')}, frameEnd={instance.data.get('frameEnd')}")
