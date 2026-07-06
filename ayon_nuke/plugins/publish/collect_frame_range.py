import pyblish.api
from ayon_core.pipeline.publish import AYONPyblishPluginMixin

class CollectRenderFrameRange(pyblish.api.InstancePlugin, AYONPyblishPluginMixin):
    """Ensure render products inherit script root frame range when custom range is not explicitly set."""

    order = pyblish.api.CollectorOrder + 0.1
    families = ["render"]
    label = "Collect Render Frame Range"

    def process(self, instance):
        # Skip if instance is not a render product with enabled custom frame range
        if not instance.data.get("customFrameRange", False):
            return

        # Get current frame range from instance data (may be None or 1-1 from default)
        frame_start = instance.data.get("frameStart")
        frame_end = instance.data.get("frameEnd")

        # If frame range is not explicitly set (e.g., defaulted to 1-1 due to bug),
        # override with script root frame range.
        if frame_start is None or frame_end is None:
            import nuke
            root = nuke.root()
            instance.data["frameStart"] = int(root.firstFrame())
            instance.data["frameEnd"] = int(root.lastFrame())
            self.log.info(
                f"Inherited script root frame range: {instance.data['frameStart']}-{instance.data['frameEnd']}"
            )
