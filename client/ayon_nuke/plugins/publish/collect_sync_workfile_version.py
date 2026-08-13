from __future__ import annotations
import pyblish.api


class CollectSyncWorkfileVersion(pyblish.api.InstancePlugin):
    """Collect sync workfile version to instance data
    after scene version is collected by CollectSceneVersion.
    """

    order = pyblish.api.CollectorOrder + 0.001
    label = "Collect Sync Workfile Version"
    hosts = ["nuke", "nukeassist"]

    settings_category = "nuke"

    # presets
    sync_workfile_version_on_product_base_types: list[str] = []

    def process(self, instance: pyblish.api.Instance):
        product_base_type: str = instance.data["productBaseType"]
        # sync workfile version
        if product_base_type not in self.sync_workfile_version_on_product_base_types:  # noqa: E501
            return

        context = instance.context
        if "version" not in context.data:
            # This may happen is workfile is not saved
            self.log.error(
                "Unable to sync workfile version, because no context version "
                "was found. Make sure workfile is saved."
            )
            return

        self.log.debug(
            f"Syncing version with workfile for '{product_base_type}'"
        )
        # get version to instance for integration
        instance.data['version'] = context.data['version']
