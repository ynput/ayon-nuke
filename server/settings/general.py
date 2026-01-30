from ayon_server.settings import BaseSettingsModel, SettingsField


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

    menu: MenuShortcut = SettingsField(
        default_factory=MenuShortcut,
        title="Menu Shortcuts",
    )


DEFAULT_GENERAL_SETTINGS = {
    "menu": {
        "create": "ctrl+alt+c",
        "publish": "ctrl+alt+p",
        "load": "ctrl+alt+l",
        "manage": "ctrl+alt+m",
        "build_workfile": "ctrl+alt+b",
        "version_up_workfile": "ctrl+alt+s",
    }
}
