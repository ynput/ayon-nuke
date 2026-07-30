from ayon_server.settings import BaseSettingsModel, SettingsField


class WorkfileCallbacks(BaseSettingsModel):
    """Callbacks to apply in Nuke."""
    on_script_create: bool = SettingsField(
        default=True,
        title="On Script Create",
        description="Apply callbacks from AYON context on new workfile",
    )
    on_script_open: bool = SettingsField(
        default=True,
        title="On Script Open",
        description="Apply callbacks from AYON context on loaded workfile.",
    )


DEFAULT_WORKFILE_CALLBACKS_SETTINGS = {
    "on_script_create": True,
    "on_script_open": True,
}
