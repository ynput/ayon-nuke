import nuke
import pyblish.api

from ayon_core.pipeline import OptionalPyblishPluginMixin
from ayon_core.lib import version_up


class IncrementScriptVersion(pyblish.api.ContextPlugin,
                             OptionalPyblishPluginMixin):
    """Increment current script version."""

    order = pyblish.api.IntegratorOrder + 0.9
    label = "Increment Script Version"
    optional = True
    families = ["workfile"]
    hosts = ["nuke"]

    settings_category = "nuke"

    def process(self, context):
        if not self.is_active(context.data):
            return

        if not context.data.get("increment_script_version", True):
            return

        assert all(result["success"] for result in context.data["results"]), (
            "Publishing not successful so version is not increased.")

        path = context.data["currentFile"]
        nuke.scriptSaveAs(version_up(path))
        self.log.info('Incrementing script version')
