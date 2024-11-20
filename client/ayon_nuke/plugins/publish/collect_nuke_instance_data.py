import nuke
import pyblish.api


class CollectInstanceData(pyblish.api.InstancePlugin):
    """Collect Nuke instance data

    """

    order = pyblish.api.CollectorOrder - 0.49
    label = "Collect Nuke Instance Data"
    hosts = ["nuke", "nukeassist"]

    settings_category = "nuke"

    # presets
    sync_workfile_version_on_families = []

    def process(self, instance):
        product_type = instance.data["productType"]

        # Get format
        root = nuke.root()
        format_ = root['format'].value()
        resolution_width = format_.width()
        resolution_height = format_.height()
        pixel_aspect = format_.pixelAspect()

        # sync workfile version
        if product_type in self.sync_workfile_version_on_families:
            self.log.debug(
                "Syncing version with workfile for '{}'".format(
                    product_type
                )
            )
            # get version to instance for integration
            instance.data['version'] = instance.context.data['version']

        instance.data.update({
            "step": 1,
            "fps": root['fps'].value(),
            "resolutionWidth": resolution_width,
            "resolutionHeight": resolution_height,
            "pixelAspect": pixel_aspect

        })

        # add creator attributes to instance
        creator_attributes = instance.data["creator_attributes"]
        instance.data.update(creator_attributes)

        # add review family if review activated on instance
        if instance.data.get("review"):
            instance.data["families"].append("review")

        # add staging dir information on instance
        staging_dir = instance.data["transientData"].get("stagingDir")
        staging_dir_persistent = instance.data["transientData"].get(
            "stagingDir_persistent", False
        )
        if staging_dir:
            instance.data.update({
                "stagingDir": staging_dir,
                "stagingDir_persistent": staging_dir_persistent
            })

        self.log.debug("Collected instance: {}".format(
            instance.data))
