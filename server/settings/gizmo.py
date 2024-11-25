from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    MultiplatformPathModel,
    MultiplatformPathListModel,
)


class SubGizmoItem(BaseSettingsModel):
    title: str = SettingsField(
        title="Label"
    )
    sourcetype: str = SettingsField(
        title="Type of usage"
    )
    command: str = SettingsField(
        title="Python command"
    )
    icon: str = SettingsField(
        title="Icon Path"
    )
    shortcut: str = SettingsField(
        title="Hotkey"
    )


class GizmoDefinitionItem(BaseSettingsModel):
    gizmo_toolbar_path: str = SettingsField(
        title="Gizmo Menu Parent",
        description="Leave it empty to use the toolbar menu name as parent."
    )
    sub_gizmo_list: list[SubGizmoItem] = SettingsField(
        default_factory=list, title="Sub Gizmo List")


def gizmo_enum_options():
    return [
        {
            "value": "gizmo_source_dir",
            "label": "Add a Gizmo Directory Path"
        },
        {
            "value": "gizmo_definition",
            "label": "Add Gizmos by Definitions"
        }
    ]


class GizmoItem(BaseSettingsModel):
    """Nuke gizmo item """

    toolbar_menu_name: str = SettingsField(
        title="Toolbar Menu Name"
    )
    toolbar_icon_path: MultiplatformPathModel = SettingsField(
        default_factory=MultiplatformPathModel,
        title="Toolbar Icon Path",
        description="Leave it empty to use the AYON icon."
    )
    options: str = SettingsField(
        "gizmo_source_dir",
        title="Gizmo Menu Options",
        description="Switch between gizmo menu options",
        enum_resolver=gizmo_enum_options,
        conditionalEnum=True,
        section="Gizmos"
    )
    gizmo_source_dir: MultiplatformPathListModel = SettingsField(
        default_factory=MultiplatformPathListModel,
        title="Gizmo Directory Path"
    )
    gizmo_definition: list[GizmoDefinitionItem] = SettingsField(
        default_factory=list, title="Gizmo Definition")


DEFAULT_GIZMO_ITEM = {
    "toolbar_menu_name": "OpenPype Gizmo",
    "gizmo_source_dir": {
        "windows": [],
        "darwin": [],
        "linux": []
    },
    "toolbar_icon_path": {
        "windows": "",
        "darwin": "",
        "linux": ""
    },
    "gizmo_definition": [
        {
            "gizmo_toolbar_path": "",
            "sub_gizmo_list": [
                {
                    "sourcetype": "python",
                    "title": "Gizmo Note",
                    "command": "nuke.nodes.StickyNote(label='You can create your own toolbar menu in the Nuke GizmoMenu of OpenPype')",
                    "icon": "",
                    "shortcut": ""
                }
            ]
        }
    ]
}
