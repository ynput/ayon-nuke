import pyblish.api
import nuke


class CollectModel(pyblish.api.InstancePlugin):
    """Collect Model node instance and its content
    """

    order = pyblish.api.CollectorOrder + 0.22
    label = "Collect Model"
    hosts = ["nuke"]
    families = ["model"]

    settings_category = "nuke"

    def process(self, instance):

        geo_node = instance.data["transientData"]["node"]

        # add product type to families
        instance.data["families"].insert(0, instance.data["productType"])
        # make label nicer
        instance.data["label"] = geo_node.name()

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
        self.log.debug("Model instance collected: `{}`".format(instance))
