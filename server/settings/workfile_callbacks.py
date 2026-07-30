from ayon_server.settings import BaseSettingsModel, SettingsField

class ContextSettings(BaseSettingsModel):
    """Nuke context settings."""

    resolution_from_context: bool = SettingsField(
        default=True,
        title="Resolution from Context",
        description="Set resolution from context on new workfile.",
    )
    frame_range_from_context: bool = SettingsField(
        default=True,
        title="Frame Range from Context",
        description="Set frame range from context on new workfile.",
    )
    colorspace_from_context: bool = SettingsField(
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
        "resolution_from_context": True,
        "frame_range_from_context": True,
        "colorspace_from_context": True,
    },
    "on_script_open": {
        "resolution_from_context": True,
        "frame_range_from_context": True,
        "colorspace_from_context": True,
    },
}
