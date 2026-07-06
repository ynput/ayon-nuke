import pyblish.api
from ayon_nuke.api import plugin
from ayon_nuke.lib import get_frame_range_attributes, set_frame_range_attributes

class PrecollectFrameRange(plugin.NukeInstancePlugin):
    """Precollect frame range for instances."""

    order = pyblish.api.CollectorOrder + 0.1
    families = ["render", "prerender"]

    def process(self, instance):
        root = instance.data["context"]["rootFrameStart"], instance.data["context"]["rootFrameEnd"]
        frame_start_attr = instance.data.get("frameStartAttr")
        frame_end_attr = instance.data.get("frameEndAttr")
        if frame_start_attr is None or frame_end_attr is None:
            # fallback to root
            instance.data["frameStartHandle"] = root[0]
            instance.data["frameEndHandle"] = root[1]
            return
        # custom frame range logic - if custom but not specified, inherit root
        custom_start = instance.data.get("customFrameStart")
        custom_end = instance.data.get("customFrameEnd")
        if custom_start is None or custom_end is None:
            instance.data["frameStartHandle"] = root[0]
            instance.data["frameEndHandle"] = root[1]
        else:
            instance.data["frameStartHandle"] = custom_start
            instance.data["frameEndHandle"] = custom_end
