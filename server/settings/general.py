from ayon_server.settings import BaseSettingsModel, SettingsField


class SettingsToApply(BaseSettingsModel):
    """Settings to apply in Nuke."""
    context_settings_on_script_create: bool = SettingsField(
        default=True,
        title="Apply context settings on script create",
    )
    context_settings_on_script_open: bool = SettingsField(
        default=True,
        title="Apply context settings on script open",
    )
    context_settings: bool = SettingsField(
        default=True,
        title="Apply context settings",
    )
    frame_range_settings: bool = SettingsField(
        default=True,
        title="Apply frame range settings",
    )
    resolution_settings: bool = SettingsField(
        default=True,
        title="Apply resolution settings",
    )
    colorspace_settings: bool = SettingsField(
        default=True,
        title="Apply colorspace settings",
    )


class MenuShortcut(BaseSettingsModel):
    """Nuke general project settings."""

    create: str = SettingsField(
        title="Create..."
    )
    publish: str = SettingsField(
        title="Publish..."
    )
    load: str = SettingsField(
        title="Load..."
    )
    manage: str = SettingsField(
        title="Manage..."
    )
    build_workfile: str = SettingsField(
        title="Build Workfile..."
    )
    version_up_workfile: str = SettingsField(
        title="Version Up Workfile"
    )


class GeneralSettings(BaseSettingsModel):
    """Nuke general project settings."""
    settings_to_apply: SettingsToApply = SettingsField(
        default_factory=SettingsToApply,
        title="Settings to apply",
    )
    menu: MenuShortcut = SettingsField(
        default_factory=MenuShortcut,
        title="Menu Shortcuts",
    )


DEFAULT_GENERAL_SETTINGS = {
    "settings_to_apply": {
        "context_settings_on_script_create": True,
        "context_settings_on_script_open": True,
        "context_settings": True,
        "frame_range_settings": True,
        "resolution_settings": True,
        "colorspace_settings": True,
    },
    "menu": {
        "create": "ctrl+alt+c",
        "publish": "ctrl+alt+p",
        "load": "ctrl+alt+l",
        "manage": "ctrl+alt+m",
        "build_workfile": "ctrl+alt+b",
        "version_up_workfile": "alt+shift+s",
    }
}
