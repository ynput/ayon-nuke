"""A module containing generic loader actions that will display in the Loader.

"""

from ayon_core.lib import Logger
from ayon_core.pipeline import load
from ayon_nuke.api import lib
from ayon_nuke.api import traits as nuke_traits

log = Logger.get_logger(__name__)


class SetFrameRangeLoader(load.LoaderPlugin):
    """Set frame range excluding pre- and post-handles"""

    product_base_types = {
        "animation",
        "camera",
        "write",
        "yeticache",
        "pointcache",
    }
    product_types = product_base_types
    representations = {"*"}
    extensions = {"*"}

    label = "Set frame range"
    order = 11
    icon = "clock-o"
    color = "white"

    def load(self, context, name, namespace, data):
        version_attributes = (
            nuke_traits.get_version_attributes_with_traits(context)
        )

        start = version_attributes.get("frameStart")
        end = version_attributes.get("frameEnd")

        log.info("start: {}, end: {}".format(start, end))
        if start is None or end is None:
            log.info("Skipping setting frame range because start or "
                     "end frame data is missing..")
            return

        lib.update_frame_range(start, end)


class SetFrameRangeWithHandlesLoader(load.LoaderPlugin):
    """Set frame range including pre- and post-handles"""

    product_base_types = {
        "animation",
        "camera",
        "write",
        "yeticache",
        "pointcache",
    }
    product_types = product_base_types
    representations = {"*"}

    label = "Set frame range (with handles)"
    order = 12
    icon = "clock-o"
    color = "white"

    def load(self, context, name, namespace, data):
        version_attributes = (
            nuke_traits.get_version_attributes_with_traits(context)
        )
        start = version_attributes.get("frameStart")
        end = version_attributes.get("frameEnd")

        if start is None or end is None:
            print("Skipping setting frame range because start or "
                  "end frame data is missing..")
            return

        # Include handles
        start -= version_attributes.get("handleStart") or 0
        end += version_attributes.get("handleEnd") or 0

        lib.update_frame_range(start, end)
