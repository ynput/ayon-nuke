import pyblish.api
import nuke


class CollectGizmo(pyblish.api.InstancePlugin):
    """Collect Gizmo (group) node instance and its content
    """

    order = pyblish.api.CollectorOrder + 0.22
    label = "Collect Gizmo (group)"
    hosts = ["nuke"]
    families = ["gizmo"]

    settings_category = "nuke"

    def process(self, instance):

        # pass staging dir data
        self._pass_staging_dir_data(instance)

        gizmo_node = instance.data["transientData"]["node"]

        # add product type to families
        instance.data["families"].insert(0, instance.data["productType"])
        # make label nicer
        instance.data["label"] = gizmo_node.name()

        # Get frame range
        handle_start = instance.context.data["handleStart"]
        handle_end = instance.context.data["handleEnd"]
        first_frame = int(nuke.root()["first_frame"].getValue())
        last_frame = int(nuke.root()["last_frame"].getValue())
        families = [instance.data["productType"]] + instance.data["families"]

        # Add version data to instance
        version_data = {
            "handleStart": handle_start,
            "handleEnd": handle_end,
            "frameStart": first_frame + handle_start,
            "frameEnd": last_frame - handle_end,
            "colorspace": nuke.root().knob('workingSpaceLUT').value(),
            "families": families,
            "productName": instance.data["productName"],
            "fps": instance.context.data["fps"]
        }

        instance.data.update({
            "versionData": version_data,
            "frameStart": first_frame,
            "frameEnd": last_frame
        })
        self.log.debug("Gizmo instance collected: `{}`".format(instance))

    def _pass_staging_dir_data(self, instance):
        staging_dir = instance.data["transientData"]["stagingDir"]
        staging_dir_persistent = instance.data["transientData"].get(
            "stagingDir_persistent", False
        )
        instance.data.update({
            "stagingDir": staging_dir,
            "stagingDir_persistent": staging_dir_persistent
        })
