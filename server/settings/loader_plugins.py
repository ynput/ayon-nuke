from ayon_server.settings import BaseSettingsModel, SettingsField


class LoaderEnabledModel(BaseSettingsModel):
    enabled: bool = SettingsField(True, title="Enabled")


class LoadImageModel(LoaderEnabledModel):
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
            "label": "Auto-detect"
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
    set_frame_range: bool = SettingsField(
        title="Set frame range to version frame range",
        description=(
            "When loading, set the node's frame range "
            "to the version's frame range."
        )
    )
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


class LoadBackdropNodesModel(LoaderEnabledModel):

    remove_nodes_from_backdrop: bool = SettingsField(
        title="Remove existing AYON backdrops when removing container"
    )


class LoadClipModel(LoaderEnabledModel):
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
    AlembicCameraLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load AlembicCamera"
    )
    AlembicModelLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load AlembicModel"
    )
    FbxCameraLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load FbxCamera"
    )
    GeoImportLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load GeoImport"
    )
    GeoReferenceLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load GeoReference"
    )
    LinkAsGroup: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load LinkAsGroup"
    )
    LoadBackdropNodes: LoadBackdropNodesModel = SettingsField(
        default_factory=LoadBackdropNodesModel,
        title="Load Backdrop Nodes"
    )
    LoadClip: LoadClipModel = SettingsField(
        default_factory=LoadClipModel,
        title="Load Clip"
    )
    LoadEffects: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load Effects"
    )
    LoadEffectsInputProcess: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load Effects Input Process"
    )
    LoadGizmo: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load Gizmo"
    )
    LoadGizmoInputProcess: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load Gizmo Input Process"
    )
    LoadImage: LoadImageModel = SettingsField(
        default_factory=LoadImageModel,
        title="Load Image"
    )
    LoadOcioLookNodes: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load Ocio Look Nodes"
    )
    MatchmoveLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load Matchmove"
    )
    SetFrameRangeLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Set Frame Range"
    )
    SetFrameRangeWithHandlesLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Set Frame Range With Handles"
    )
    UsdCameraLoader: LoaderEnabledModel = SettingsField(
        default_factory=LoaderEnabledModel,
        title="Load USD Camera"
    )


DEFAULT_LOADER_PLUGINS_SETTINGS = {
    "AlembicCameraLoader": {
        "enabled": True
    },
    "AlembicModelLoader": {
        "enabled": True
    },
    "FbxCameraLoader": {
        "enabled": True
    },
    "GeoImportLoader": {
        "enabled": True
    },
    "GeoReferenceLoader": {
        "enabled": True
    },
    "LinkAsGroup": {
        "enabled": True
    },
    "LoadBackdropNodes": {
        "enabled": True,
        "remove_nodes_from_backdrop": False
    },
    "LoadClip": {
        "enabled": True,
        "representations_include": [],
        "node_name_template": "{class_name}_{ext}",
        "options_defaults": {
            "set_frame_range": True,
            "start_at_workfile": False,
            "add_retime": True,
            "node_type": "auto"
        }
    },
    "LoadEffects": {
        "enabled": True
    },
    "LoadEffectsInputProcess": {
        "enabled": True
    },
    "LoadGizmo": {
        "enabled": True
    },
    "LoadGizmoInputProcess": {
        "enabled": True
    },
    "LoadImage": {
        "enabled": True,
        "representations_include": [],
        "node_name_template": "{class_name}_{ext}"
    },
    "LoadOcioLookNodes": {
        "enabled": True
    },
    "MatchmoveLoader": {
        "enabled": True
    },
    "SetFrameRangeLoader": {
        "enabled": True
    },
    "SetFrameRangeWithHandlesLoader": {
        "enabled": True
    },
    "UsdCameraLoader": {
        "enabled": True
    },
}
