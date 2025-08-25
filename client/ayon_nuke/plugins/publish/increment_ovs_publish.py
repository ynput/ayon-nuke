import nuke
import pyblish.api
import os

from ayon_core.pipeline import OptionalPyblishPluginMixin
from ayon_core.lib import version_up
import version


class IncrementOvsPublish(pyblish.api.ContextPlugin,
                             OptionalPyblishPluginMixin):
    """Increment current script version if the publish is utilizing an ovs write."""

    order = pyblish.api.IntegratorOrder + 4.5
    label = "Increment OVS Script Version"
    optional = True
    families = ["render"]
    hosts = ["nuke"]

    settings_category = "nuke"

    def process(self, context):
        if not self.is_active(context.data):
            return

        if not context.data.get("increment_ovs_publish", True):
            return

        ovs_count = 0
        for instance in context:
            is_ovs = instance.data.get("is_ovs", False)
            self.log.info(f"Instance {instance} Ovs Status: {is_ovs}")
            if is_ovs:
                ovs_count += 1

        assert all(result["success"] for result in context.data["results"]), (
            "Publishing not successful so version is not increased.")

        if ovs_count > 0:
            self.log.info(f"Found {ovs_count} OVS instances.")
            path = context.data["currentFile"]
            versioned_path = version_up(path)
            nuke.scriptSaveAs(versioned_path)
            self.log.info('Incrementing script version due to ovs render having version dependant render output')

        else:
            self.log.info('No OVS instances found, skipping script version increment.')
            return