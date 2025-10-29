from ayon_server.settings import BaseSettingsModel, SettingsField


class LoaderEnabledModel(BaseSettingsModel):
    enabled: bool = SettingsField(True, title="Enabled")


class LoadImageModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        title="Enabled"
    )
    representations_include: list[str] = SettingsField(
        default_factory=list,
        title="Include representations"
    )

    node_name_template: str = SettingsField(
        title="Read node name template"
    )


def node_type_enum_options():
    return [
        {
            "value": "auto",
            "label": "auto"
        },        
        {
            "value": "Read",
            "label": "Read"
        },
        {
            "value": "DeepRead",
            "label": "DeepRead"
        }
    ]

class LoadClipOptionsModel(BaseSettingsModel):
    start_at_workfile: bool = SettingsField(
        title="Start at workfile's start frame"
    )
    add_retime: bool = SettingsField(
        title="Add retime"
    )
    node_type: str = SettingsField(
        title="Read Node Type",
        enum_resolver=node_type_enum_options,
        default="auto",
    )

class LoadClipModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        title="Enabled"
    )
    representations_include: list[str] = SettingsField(
        default_factory=list,
        title="Include representations"
    )

    node_name_template: str = SettingsField(
        title="Read node name template"
    )
    options_defaults: LoadClipOptionsModel = SettingsField(
        default_factory=LoadClipOptionsModel,
        title="Loader option defaults"
    )


class LoaderPluginsModel(BaseSettingsModel):
    LoadImage: LoadImageModel = SettingsField(
        default_factory=LoadImageModel,
        title="Load Image"
    )
    LoadClip: LoadClipModel = SettingsField(
        default_factory=LoadClipModel,
        title="Load Clip"
    )
    GeoImportLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load GeoImport"
    )
    GeoReferenceLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load GeoReference"
    )


DEFAULT_LOADER_PLUGINS_SETTINGS = {
    "LoadImage": {
        "enabled": True,
        "representations_include": [],
        "node_name_template": "{class_name}_{ext}"
    },
    "LoadClip": {
        "enabled": True,
        "representations_include": [],
        "node_name_template": "{class_name}_{ext}",
        "options_defaults": {
            "start_at_workfile": False,
            "add_retime": True,
            "deep_exr": False
        }
    },
    "GeoImportLoader": {
        "enabled": True
    },
    "GeoReferenceLoader": {
        "enabled": True
    }
}
