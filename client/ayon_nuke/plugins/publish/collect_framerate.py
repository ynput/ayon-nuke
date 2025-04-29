import nuke

import pyblish.api


class CollectFramerate(pyblish.api.ContextPlugin):
    """Collect framerate."""

    order = pyblish.api.CollectorOrder
    label = "Collect Framerate"
    hosts = [
        "nuke",
        "nukeassist"
    ]

    settings_category = "nuke"

    def process(self, context):
        context.data["fps"] = nuke.root()["fps"].getValue()
