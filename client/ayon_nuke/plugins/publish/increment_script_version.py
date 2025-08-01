import os

import pyblish.api

from ayon_core.lib import version_up
from ayon_core.host import IWorkfileHost
from ayon_core.pipeline import registered_host, OptionalPyblishPluginMixin


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

        current_filepath = context.data["currentFile"]
        host: IWorkfileHost = registered_host()
        try:
            # Function 'save_next_version' was introduced in ayon-core 1.5.0
            from ayon_core.pipeline.workfile import save_next_version
            from ayon_core.host.interfaces import SaveWorkfileOptionalData

            current_filename = os.path.basename(current_filepath)
            save_next_version(
                description=(
                    f"Incremented by publishing from {current_filename}"
                ),
                # Optimize the save by reducing needed queries for context
                prepared_data=SaveWorkfileOptionalData(
                    project_entity=context.data["projectEntity"],
                    project_settings=context.data["project_settings"],
                    anatomy=context.data["anatomy"],
                )
            )
        except ImportError:
            # Backwards compatibility before ayon-core 1.5.0
            self.log.debug(
                "Using legacy `version_up`. Update AYON core addon to "
                "use newer `save_next_version` function."
            )
            new_filepath = version_up(current_filepath)
            host.save_workfile(new_filepath)

        new_filepath = host.get_current_workfile()
        self.log.debug(f"Incremented script version to: {new_filepath}")
