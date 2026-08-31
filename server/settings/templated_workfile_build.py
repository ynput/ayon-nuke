from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    task_types_enum,
)


class TemplatedWorkfileProfileModel(BaseSettingsModel):
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
        enum_resolver=task_types_enum
    )
    task_names: list[str] = SettingsField(
        default_factory=list,
        title="Task names"
    )
    path: str = SettingsField(
        title="Path to template"
    )
    keep_placeholder: bool = SettingsField(
        False,
        title="Keep placeholders")
    create_first_version: bool = SettingsField(
        True,
        title="Save first workfile version",
        description=(
            "Automatically create the first version "
            "of the workfile based on the template upon saving."
        )
    )


class TemplatedWorkfileBuildModel(BaseSettingsModel):
    """Settings for templated workfile builder."""
    profiles: list[TemplatedWorkfileProfileModel] = SettingsField(
        default_factory=list
    )
