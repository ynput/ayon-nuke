from ayon_server.settings import BaseSettingsModel, SettingsField

class ContextSettings(BaseSettingsModel):
    """Nuke context settings."""

    set_resolution: bool = SettingsField(
        default=True,
        title="Resolution from Context",
        description="Set resolution from context on new workfile.",
    )
    set_frame_range: bool = SettingsField(
        default=True,
        title="Frame Range from Context",
        description="Set frame range from context on new workfile.",
    )
    set_colorspace: bool = SettingsField(
        default=True,
        title="Colorspace from Context",
        description="Set colorspace from context on new workfile.",
    )


class WorkfileCallbacks(BaseSettingsModel):
    """Callbacks to apply in Nuke."""
    on_script_create: ContextSettings = SettingsField(
        default_factory=ContextSettings,
        title="On Script Create",
        description="Apply callbacks from AYON context on new workfile",
    )
    on_script_open: ContextSettings = SettingsField(
        default_factory=ContextSettings,
        title="On Script Open",
        description="Apply callbacks from AYON context on loaded workfile.",
    )


DEFAULT_WORKFILE_CALLBACKS_SETTINGS = {
    "on_script_create": {
        "set_resolution": True,
        "set_frame_range": True,
        "set_colorspace": True,
    },
    "on_script_open": {
        "set_resolution": True,
        "set_frame_range": True,
        "set_colorspace": True,
    },
}
