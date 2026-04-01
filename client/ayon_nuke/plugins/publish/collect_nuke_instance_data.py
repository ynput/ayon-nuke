from __future__ import annotations
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
    sync_workfile_version_on_product_base_types: list[str] = []

    def process(self, instance):
        product_base_type = instance.data["productBaseType"]

        # Get format
        root = nuke.root()
        format_ = root['format'].value()
        resolution_width = format_.width()
        resolution_height = format_.height()
        pixel_aspect = format_.pixelAspect()

        # sync workfile version
        if product_base_type in self.sync_workfile_version_on_product_base_types:  # noqa: E501
            self.log.debug(
                "Syncing version with workfile for '{}'".format(
                    product_base_type
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
        staging_dir_is_custom = instance.data["transientData"].get(
            "stagingDir_is_custom", False
        )
        if staging_dir:
            instance.data.update({
                "stagingDir": staging_dir,
                "stagingDir_persistent": staging_dir_persistent,
                "stagingDir_is_custom": staging_dir_is_custom,
            })

        self.log.debug("Collected instance: {}".format(
            instance.data))
