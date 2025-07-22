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
        new_filepath = version_up(current_filepath)

        host: IWorkfileHost = registered_host()
        if hasattr(host, "save_workfile_with_context"):
            from ayon_core.host.interfaces import SaveWorkfileOptionalData
            host.save_workfile_with_context(
                filepath=new_filepath,
                folder_entity=context.data["folderEntity"],
                task_entity=context.data["taskEntity"],
                description="Incremented by publishing.",
                # Optimize the save by reducing needed queries for context
                prepared_data=SaveWorkfileOptionalData(
                    project_entity=context.data["projectEntity"],
                    project_settings=context.data["project_settings"],
                    anatomy=context.data["anatomy"],
                )
            )
        else:
            # Backwards compatibility before:
            # https://github.com/ynput/ayon-core/pull/1275
            host.save_workfile(new_filepath)

        self.log.debug(f"Incremented script version to: {new_filepath}")
