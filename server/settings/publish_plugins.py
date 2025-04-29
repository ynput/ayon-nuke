from pydantic import validator
from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    ensure_unique_names,
    task_types_enum
)
from .common import (
    KnobModel,
    ColorspaceConfigurationModel,
    validate_json_dict,
)


def nuke_render_publish_types_enum():
    """Return all nuke render families available in creators."""
    return [
        {"value": "render", "label": "Render"},
        {"value": "prerender", "label": "Prerender"},
        {"value": "image", "label": "Image"}
    ]


def nuke_product_types_enum():
    """Return all nuke families available in creators."""
    return [
        {"value": "nukenodes", "label": "Nukenodes"},
        {"value": "model", "label": "Model"},
        {"value": "camera", "label": "Camera"},
        {"value": "gizmo", "label": "Gizmo"},
        {"value": "source", "label": "Source"}
    ] + nuke_render_publish_types_enum()


def nuke_export_formats_enum():
    """Return all nuke export format available in creators."""
    return [
        {"value": "abc", "label": "Alembic"},
        {"value": "fbx", "label": "FBX"},    
    ]


class NodeModel(BaseSettingsModel):
    name: str = SettingsField(
        title="Node name"
    )
    nodeclass: str = SettingsField(
        "",
        title="Node class"
    )
    dependent: str = SettingsField(
        "",
        title="Incoming dependency"
    )
    knobs: list[KnobModel] = SettingsField(
        default_factory=list,
        title="Knobs",
    )

    @validator("knobs")
    def ensure_unique_names(cls, value):
        """Ensure name fields within the lists have unique names."""
        ensure_unique_names(value)
        return value


class CollectInstanceDataModel(BaseSettingsModel):
    sync_workfile_version_on_product_types: list[str] = SettingsField(
        default_factory=list,
        enum_resolver=nuke_product_types_enum,
        title="Product types"
    )


class OptionalPluginModel(BaseSettingsModel):
    enabled: bool = SettingsField(True)
    optional: bool = SettingsField(title="Optional")
    active: bool = SettingsField(title="Active")


class ValidateKnobsModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    knobs: str = SettingsField(
        "{}",
        title="Knobs",
        widget="textarea",
    )

    @validator("knobs")
    def validate_json(cls, value):
        return validate_json_dict(value)


class ExtractReviewDataModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")


class ExtractReviewDataLutModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")


class BakingStreamFilterModel(BaseSettingsModel):
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
        enum_resolver=task_types_enum
    )
    product_types: list[str] = SettingsField(
        default_factory=list,
        enum_resolver=nuke_render_publish_types_enum,
        title="Sync workfile versions for familes"
    )
    product_names: list[str] = SettingsField(
        default_factory=list, title="Product names")


class ReformatNodesRepositionNodes(BaseSettingsModel):
    node_class: str = SettingsField(title="Node class")
    knobs: list[KnobModel] = SettingsField(
        default_factory=list,
        title="Node knobs")


class ReformatNodesConfigModel(BaseSettingsModel):
    """Only reposition nodes supported.

    You can add multiple reformat nodes and set their knobs.
    Order of reformat nodes is important. First reformat node will
    be applied first and last reformat node will be applied last.
    """
    enabled: bool = SettingsField(False)
    reposition_nodes: list[ReformatNodesRepositionNodes] = SettingsField(
        default_factory=list,
        title="Reposition knobs"
    )


class IntermediateOutputModel(BaseSettingsModel):
    name: str = SettingsField(title="Output name")
    publish: bool = SettingsField(title="Publish")
    filter: BakingStreamFilterModel = SettingsField(
        title="Filter", default_factory=BakingStreamFilterModel)
    read_raw: bool = SettingsField(
        False,
        title="Input read node RAW switch"
    )
    bake_viewer_process: bool = SettingsField(
        True,
        title="Bake viewer process",
        section="Baking target",
    )
    colorspace_override: ColorspaceConfigurationModel = SettingsField(
        title="Target baking colorspace override",
        description="Override Baking target with colorspace or display/view",
        default_factory=ColorspaceConfigurationModel
    )
    bake_viewer_input_process: bool = SettingsField(
        True,
        title="Bake viewer input process node (LUT)",
        section="Baking additional",
    )
    reformat_nodes_config: ReformatNodesConfigModel = SettingsField(
        default_factory=ReformatNodesConfigModel,
        title="Reformat Nodes")
    extension: str = SettingsField(
        "mov",
        title="File extension"
    )
    add_custom_tags: list[str] = SettingsField(
        title="Custom tags", default_factory=list)


class ExtractReviewIntermediatesModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    viewer_lut_raw: bool = SettingsField(title="Viewer lut raw")
    outputs: list[IntermediateOutputModel] = SettingsField(
        default_factory=list,
        title="Baking streams"
    )


class FSubmissionNoteModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="enabled")
    template: str = SettingsField(title="Template")


class FSubmistingForModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="enabled")
    template: str = SettingsField(title="Template")


class FVFXScopeOfWorkModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="enabled")
    template: str = SettingsField(title="Template")


class ExtractCameraFormatModel(BaseSettingsModel):
    export_camera_format: str = SettingsField(
        enum_resolver=nuke_export_formats_enum,
        conditionalEnum=True,
        title="Camera export format",
        description="Switch between different camera export formats",
    )


class ExctractSlateFrameParamModel(BaseSettingsModel):
    f_submission_note: FSubmissionNoteModel = SettingsField(
        title="f_submission_note",
        default_factory=FSubmissionNoteModel
    )
    f_submitting_for: FSubmistingForModel = SettingsField(
        title="f_submitting_for",
        default_factory=FSubmistingForModel
    )
    f_vfx_scope_of_work: FVFXScopeOfWorkModel = SettingsField(
        title="f_vfx_scope_of_work",
        default_factory=FVFXScopeOfWorkModel
    )


class ExtractSlateFrameModel(BaseSettingsModel):
    viewer_lut_raw: bool = SettingsField(title="Viewer lut raw")
    key_value_mapping: ExctractSlateFrameParamModel = SettingsField(
        title="Key value mapping",
        default_factory=ExctractSlateFrameParamModel
    )


class IncrementScriptVersionModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    optional: bool = SettingsField(title="Optional")
    active: bool = SettingsField(title="Active")


class PublishPluginsModel(BaseSettingsModel):
    CollectInstanceData: CollectInstanceDataModel = SettingsField(
        title="Collect Instance Version",
        default_factory=CollectInstanceDataModel,
        section="Collectors"
    )
    ValidateCorrectAssetContext: OptionalPluginModel = SettingsField(
        title="Validate Correct Folder Name",
        default_factory=OptionalPluginModel,
        section="Validators"
    )
    ValidateKnobs: ValidateKnobsModel = SettingsField(
        title="Validate Knobs",
        default_factory=ValidateKnobsModel
    )
    ValidateOutputResolution: OptionalPluginModel = SettingsField(
        title="Validate Output Resolution",
        default_factory=OptionalPluginModel
    )
    ValidateGizmo: OptionalPluginModel = SettingsField(
        title="Validate Gizmo",
        default_factory=OptionalPluginModel
    )
    ValidateBackdrop: OptionalPluginModel = SettingsField(
        title="Validate Backdrop",
        default_factory=OptionalPluginModel
    )
    ValidateScriptAttributes: OptionalPluginModel = SettingsField(
        title="Validate workfile attributes",
        default_factory=OptionalPluginModel
    )
    ExtractReviewData: ExtractReviewDataModel = SettingsField(
        title="Extract Review Data",
        default_factory=ExtractReviewDataModel
    )
    ExtractReviewDataLut: ExtractReviewDataLutModel = SettingsField(
        title="Extract Review Data Lut",
        default_factory=ExtractReviewDataLutModel
    )
    ExtractReviewIntermediates: ExtractReviewIntermediatesModel = (
        SettingsField(
            title="Extract Review Intermediates",
            default_factory=ExtractReviewIntermediatesModel
        )
    )
    ExtractCameraFormat: ExtractCameraFormatModel = SettingsField(
        title="Extract Camera Format",
        default_factory=ExtractCameraFormatModel        
    )
    ExtractSlateFrame: ExtractSlateFrameModel = SettingsField(
        title="Extract Slate Frame",
        default_factory=ExtractSlateFrameModel
    )
    IncrementScriptVersion: IncrementScriptVersionModel = SettingsField(
        title="Increment Workfile Version",
        default_factory=IncrementScriptVersionModel,
        section="Integrators"
    )


DEFAULT_PUBLISH_PLUGIN_SETTINGS = {
    "CollectInstanceData": {
        "sync_workfile_version_on_product_types": [
            "nukenodes",
            "camera",
            "gizmo",
            "source",
            "render",
            "write"
        ]
    },
    "ValidateCorrectAssetContext": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateKnobs": {
        "enabled": False,
        "knobs": "\n".join([
            '{',
            '    "render": {',
            '        "review": true',
            '    }',
            '}'
        ])
    },
    "ValidateOutputResolution": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateGizmo": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateBackdrop": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateScriptAttributes": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ExtractReviewData": {
        "enabled": False
    },
    "ExtractReviewDataLut": {
        "enabled": False
    },
    "ExtractReviewIntermediates": {
        "enabled": True,
        "viewer_lut_raw": False,
        "outputs": [
            {
                "name": "baking",
                "publish": False,
                "filter": {
                    "task_types": [],
                    "product_types": [],
                    "product_names": []
                },
                "read_raw": False,
                "colorspace_override": {
                    "enabled": False,
                    "type": "colorspace",
                    "colorspace": "",
                    "display_view": {
                        "display": "",
                        "view": ""
                    }
                },
                "bake_viewer_process": True,
                "bake_viewer_input_process": True,
                "reformat_nodes_config": {
                    "enabled": False,
                    "reposition_nodes": [
                        {
                            "node_class": "Reformat",
                            "knobs": [
                                {
                                    "type": "text",
                                    "name": "type",
                                    "text": "to format"
                                },
                                {
                                    "type": "text",
                                    "name": "format",
                                    "text": "HD_1080"
                                },
                                {
                                    "type": "text",
                                    "name": "filter",
                                    "text": "Lanczos6"
                                },
                                {
                                    "type": "boolean",
                                    "name": "black_outside",
                                    "boolean": True
                                },
                                {
                                    "type": "boolean",
                                    "name": "pbb",
                                    "boolean": False
                                }
                            ]
                        }
                    ]
                },
                "extension": "mov",
                "add_custom_tags": []
            }
        ]
    },
    "ExtractCameraFormat": {
        "export_camera_format": "abc",
    },
    "ExtractSlateFrame": {
        "viewer_lut_raw": False,
        "key_value_mapping": {
            "f_submission_note": {
                "enabled": True,
                "template": "{comment}"
            },
            "f_submitting_for": {
                "enabled": True,
                "template": "{intent[value]}"
            },
            "f_vfx_scope_of_work": {
                "enabled": False,
                "template": ""
            }
        }
    },
    "IncrementScriptVersion": {
        "enabled": True,
        "optional": True,
        "active": True
    }
}
