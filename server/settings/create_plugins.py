from pydantic import validator
from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    ensure_unique_names,
    task_types_enum,
)
from .common import KnobModel

INSTANCE_ATTRIBUTES_DESCRIPTION: str = (
    """Allows to enable or disable certain features for the instance:
    - Reviewable: Mark the output as reviewable, allowing transcoding and
        e.g. uploading as reviewable to production tracker (depending on
        what tags are sets for reviewables)
    - Farm rendering: Enables the setting to render the output on the farm.
        The artist can still decide to render locally or on the farm using
        attributes in the publisher UI.
    - Use range Limit: Enables the write node to use the range limit from
        the created parent instance render node, so that this write node
        ONLY renders the frames within the frame range.
    - Render On Farm: Adds a button on the Nuke node that will submit the
        render of the write node to the farm **without** triggering the
        regular publish logic. This is useful for quick test renders.
    - Slate Generation: When enabled, a slate frame is generated and
        prepended to the rendered sequence before publishing.
        Slater addon is required
    - Conditional Reviewable: When enabled, the output is marked as reviewable
    only under certain conditions.
    """
)

PRENODES_LIST_DESCRIPTION: str = (
    """List of nodes that should be added before the write node."""
)

RENDER_TARGET_DESCRIPTION: str = (
    "Set default render target for renders.\n\n"
    "Note: The *farm* related options are only valid if instance attributes "
    "includes 'Farm Rendering'."
)
DISABLE_REVIEW_TOGGLE_DESCRIPTION: str = (
    "At which task types context should the `Review` toggle be is showing. "
    "Select no Task Type to show it on all of them."
)


def validate_instance_attributes(value):
    """Ensure reviewable and conditional_reviewable are exclusive."""
    if "reviewable" in value and "conditional_reviewable" in value:
        raise ValueError(
            "'Reviewable' and 'Conditional Reviewable' cannot be "
            "selected together."
        )
    return value


def instance_attributes_enum():
    """Return create write instance attributes."""
    return [
        {"value": "reviewable", "label": "Reviewable"},
        {"value": "farm_rendering", "label": "Farm rendering"},
        {"value": "use_range_limit", "label": "Use range limit"},
        {"value": "render_on_farm", "label": "Render On Farm"},
        {"value": "slate_gen", "label": "Slate Generation"},
        {"value": "conditional_reviewable", "label": "Conditional Reviewable"}
    ]


def render_target_enum():
    """Return write render target enum."""
    return [
        {"value": "local", "label": "Local machine rendering"},
        {"value": "frames", "label": "Use existing frames"},
        {"value": "frames_farm", "label": "Use existing frames - farm"},
        {"value": "farm", "label": "Farm rendering"}
    ]


class ConditionalReviewableModel(BaseSettingsModel):
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
        enum_resolver=task_types_enum
    )


class PrenodeModel(BaseSettingsModel):
    name: str = SettingsField(
        title="Node name",
        description=(
            "Node name, use this as the name in 'Incoming dependency' on other"
            " preceding nodes if a connection is needed."
        )
    )
    nodeclass: str = SettingsField(
        "",
        title="Node class",
        description="Nuke node class (type) of the node to add."
    )
    dependent: str = SettingsField(
        "",
        title="Incoming dependency",
        description=(
            "Input node name of another preceding node that should"
            "come before this node."
        ),
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


class ProductTypeItemModel(BaseSettingsModel):
    _layout = "compact"
    product_type: str = SettingsField(
        title="Product type",
        description="Product type name"
    )
    label: str = SettingsField(
        "",
        title="Label",
        description="Label to show in UI for the product type"
    )


class DefaultPluginModel(BaseSettingsModel):
    enabled: bool = SettingsField(
        True, title="Enabled", description="Enable or disable the plugin"
    )
    order: int = SettingsField(
        100, title="Order", description="Order of the plugin in the list"
    )
    product_type_items: list[ProductTypeItemModel] = SettingsField(
        default_factory=list,
        title="Product type items",
        description=(
            "Optional list of product types this plugin can create. "
        ),
    )


class CreateWriteRenderModel(DefaultPluginModel):
    temp_rendering_path_template: str = SettingsField(
        title="Temporary rendering path template"
    )
    default_variants: list[str] = SettingsField(
        title="Default variants",
        default_factory=list
    )
    instance_attributes: list[str] = SettingsField(
        default_factory=list,
        enum_resolver=instance_attributes_enum,
        title="Instance attributes",
        description=INSTANCE_ATTRIBUTES_DESCRIPTION,
        conditional_enum=True,
    )
    conditional_reviewable: ConditionalReviewableModel = SettingsField(
        default_factory=ConditionalReviewableModel,
        title="Conditional Reviewable Profiles",
        description=DISABLE_REVIEW_TOGGLE_DESCRIPTION,
    )
    render_target: str = SettingsField(
        enum_resolver=render_target_enum,
        conditional_enum=True,
        title="Render target",
        description=RENDER_TARGET_DESCRIPTION,
    )
    exposed_knobs: list[str] = SettingsField(
        title="Write Node Exposed Knobs",
        default_factory=list
    )
    prenodes: list[PrenodeModel] = SettingsField(
        default_factory=list,
        title="Preceding nodes",
        description=PRENODES_LIST_DESCRIPTION
    )

    @validator("prenodes")
    def ensure_unique_names(cls, value):
        """Ensure name fields within the lists have unique names."""
        ensure_unique_names(value)
        return value

    @validator("instance_attributes")
    def validate_instance_attributes(cls, value):
        """Ensure reviewable and conditional_reviewable are exclusive."""
        return validate_instance_attributes(value)


class CreateWritePrerenderModel(DefaultPluginModel):
    temp_rendering_path_template: str = SettingsField(
        title="Temporary rendering path template"
    )
    default_variants: list[str] = SettingsField(
        title="Default variants",
        default_factory=list
    )
    instance_attributes: list[str] = SettingsField(
        default_factory=list,
        enum_resolver=instance_attributes_enum,
        title="Instance attributes",
        description = INSTANCE_ATTRIBUTES_DESCRIPTION
    )
    conditional_reviewable: ConditionalReviewableModel = SettingsField(
        default_factory=ConditionalReviewableModel,
        title="Conditional Reviewable Profiles",
        description=DISABLE_REVIEW_TOGGLE_DESCRIPTION,
        conditional_enum=True,
    )
    render_target: str = SettingsField(
        enum_resolver=render_target_enum,
        conditional_enum=True,
        title="Render target",
        description=RENDER_TARGET_DESCRIPTION,
    )
    exposed_knobs: list[str] = SettingsField(
        title="Write Node Exposed Knobs", default_factory=list
    )
    prenodes: list[PrenodeModel] = SettingsField(
        default_factory=list,
        title="Preceding nodes",
        description=PRENODES_LIST_DESCRIPTION,
    )

    @validator("prenodes")
    def ensure_unique_names(cls, value):
        """Ensure name fields within the lists have unique names."""
        ensure_unique_names(value)
        return value

    @validator("instance_attributes")
    def validate_instance_attributes(cls, value):
        """Ensure reviewable and conditional_reviewable are exclusive."""
        return validate_instance_attributes(value)


class CreateWriteImageModel(DefaultPluginModel):
    temp_rendering_path_template: str = SettingsField(
        title="Temporary rendering path template"
    )
    default_variants: list[str] = SettingsField(
        title="Default variants",
        default_factory=list
    )
    instance_attributes: list[str] = SettingsField(
        default_factory=list,
        enum_resolver=instance_attributes_enum,
        title="Instance attributes"
    )
    conditional_reviewable: ConditionalReviewableModel = SettingsField(
        default_factory=ConditionalReviewableModel,
        title="Conditional Reviewable Profiles",
        description=DISABLE_REVIEW_TOGGLE_DESCRIPTION,
        conditional_enum=True,
    )
    render_target: str = SettingsField(
        enum_resolver=render_target_enum,
        conditional_enum=True,
        title="Render target",
        description=RENDER_TARGET_DESCRIPTION,
    )
    exposed_knobs: list[str] = SettingsField(
        title="Write Node Exposed Knobs",
        default_factory=list
    )
    prenodes: list[PrenodeModel] = SettingsField(
        default_factory=list,
        title="Preceding nodes",
        description=PRENODES_LIST_DESCRIPTION,
    )

    @validator("prenodes")
    def ensure_unique_names(cls, value):
        """Ensure name fields within the lists have unique names."""
        ensure_unique_names(value)
        return value

    @validator("instance_attributes")
    def validate_instance_attributes(cls, value):
        """Ensure reviewable and conditional_reviewable are exclusive."""
        return validate_instance_attributes(value)


class CreateWorkfileModel(BaseSettingsModel):
    is_mandatory: bool = SettingsField(
        default=False,
        title="Mandatory workfile",
        description=(
            "Workfile cannot be disabled by user in UI."
            " Requires core addon 1.4.1 or newer."
        )
    )


class CreatorPluginsSettings(BaseSettingsModel):
    CreateWriteRender: CreateWriteRenderModel = SettingsField(
        default_factory=CreateWriteRenderModel,
        title="Render (write)"
    )
    CreateWritePrerender: CreateWritePrerenderModel = SettingsField(
        default_factory=CreateWritePrerenderModel,
        title="Prerender (write)"
    )
    CreateWriteImage: CreateWriteImageModel = SettingsField(
        default_factory=CreateWriteImageModel,
        title="Image (write)"
    )
    CreateBackdrop: DefaultPluginModel = SettingsField(
        default_factory=DefaultPluginModel,
        title="Nukenodes (backdrop)"
    )
    CreateCamera: DefaultPluginModel = SettingsField(
        default_factory=DefaultPluginModel,
        title="Camera (3d)"
    )
    CreateGizmo: DefaultPluginModel = SettingsField(
        default_factory=DefaultPluginModel,
        title="Gizmo (group)"
    )
    CreateSilhouetteShapes: DefaultPluginModel = SettingsField(
        default_factory=DefaultPluginModel,
        title="Shapes (Silhouette .fxs)",
        description=(
            "Export .fxs shape format data file used by Boris FX Silhouette"
        )
    )
    CreateModel: DefaultPluginModel = SettingsField(
        default_factory=DefaultPluginModel,
        title="Model (3d)"
    )
    CreateSource: DefaultPluginModel = SettingsField(
        default_factory=DefaultPluginModel,
        title="Source (read)"
    )
    WorkfileCreator: CreateWorkfileModel = SettingsField(
        default_factory=CreateWorkfileModel,
        title="Create Workfile"
    )


DEFAULT_CREATE_SETTINGS = {
    "CreateWriteRender": {
        "enabled": True,
        "order": 100,
        "temp_rendering_path_template": "{work}/renders/nuke/{product[name]}/{product[name]}.{frame}.{ext}",  # noqa: E501
        "default_variants": [
            "Main",
            "Mask"
        ],
        "instance_attributes": [
            "reviewable",
            "farm_rendering"
        ],
        "disable_review_toggle_for_task_types": [],
        "render_target": "local",
        "conditional_reviewable": [],
        "exposed_knobs": [],
        "prenodes": [
            {
                "name": "Reformat01",
                "nodeclass": "Reformat",
                "dependent": "",
                "knobs": [
                    {
                        "type": "text",
                        "name": "resize",
                        "text": "none"
                    },
                    {
                        "type": "boolean",
                        "name": "black_outside",
                        "boolean": True
                    }
                ]
            }
        ]
    },
    "CreateWritePrerender": {
        "enabled": True,
        "order": 100,
        "temp_rendering_path_template": "{work}/renders/nuke/{product[name]}/{product[name]}.{frame}.{ext}",  # noqa: E501
        "default_variants": [
            "Key01",
            "Bg01",
            "Fg01",
            "Branch01",
            "Part01"
        ],
        "instance_attributes": [
            "farm_rendering",
            "use_range_limit"
        ],
        "conditional_reviewable": [],
        "render_target": "local",
        "exposed_knobs": [],
        "prenodes": []
    },
    "CreateWriteImage": {
        "enabled": True,
        "order": 100,
        "temp_rendering_path_template": "{work}/renders/nuke/{product[name]}/{product[name]}.{ext}",  # noqa: E501
        "default_variants": [
            "StillFrame",
            "MPFrame",
            "LayoutFrame"
        ],
        "instance_attributes": [
            "use_range_limit"
        ],
        "conditional_reviewable": [],
        "render_target": "local",
        "exposed_knobs": [],
        "prenodes": [
            {
                "name": "FrameHold01",
                "nodeclass": "FrameHold",
                "dependent": "",
                "knobs": [
                    {
                        "type": "expression",
                        "name": "first_frame",
                        "expression": "parent.first"
                    }
                ]
            }
        ]
    },
    "CreateBackdrop": {
        "enabled": True,
        "order": 100,
    },
    "CreateCamera": {
        "enabled": True,
        "order": 100,
    },
    "CreateGizmo": {
        "enabled": True,
        "order": 100,
    },
    "CreateSilhouetteShapes": {
        "enabled": True,
        "order": 100,
    },
    "CreateModel": {
        "enabled": True,
        "order": 100,
    },
    "CreateSource": {
        "enabled": True,
        "order": 100,
    },
}
