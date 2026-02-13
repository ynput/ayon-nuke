import nuke

from ayon_nuke.api import plugin
from ayon_nuke.api.lib import (
    maintained_selection,
    get_avalon_knob_data,
    set_avalon_knob_data,
    swap_node_with_dependency,
)


class LoadGizmo(plugin.NukeGroupLoader):
    """Loading nuke Gizmo"""

    product_base_types = {"gizmo", "lensDistortion"}
    product_types = product_base_types
    representations = {"*"}
    extensions = {"nk"}

    label = "Load Gizmo"
    order = 0
    icon = "dropbox"
    color = "white"

    node_color = "0x75338eff"

    def _create_group(self, object_name: str, context: dict):
        file = self.filepath_from_context(context).replace("\\", "/")

        # add group from nk
        nuke.nodePaste(file)

        group_node = nuke.selectedNode()
        group_node["name"].setValue(object_name)

        return group_node

    def on_load(self, group_node, namespace, context):
        # Do no post process on load, because `_create_group` did the work
        # for us already
        pass

    def on_update(self, group_node, namespace, context):
        file = self.filepath_from_context(context).replace("\\", "/")

        # Replace the group with the new group from a new file 'paste'
        # into the current comp
        avalon_data = get_avalon_knob_data(group_node)
        with maintained_selection([group_node]):
            # insert nuke script to the script
            nuke.nodePaste(file)
            # convert imported to selected node
            new_group_node = nuke.selectedNode()
            # swap nodes with maintained connections
            with swap_node_with_dependency(
                    group_node, new_group_node) as node_name:
                new_group_node["name"].setValue(node_name)

                # Transfer data to the new group
                set_avalon_knob_data(new_group_node, avalon_data)

        return new_group_node


class LoadGizmoInputProcess(LoadGizmo):
    """Loading Nuke Gizmo and connect to active viewer"""

    product_base_types = {"gizmo"}
    product_types = product_base_types

    label = "Load Gizmo - Input Process"
    icon = "eye"
    color = "#cc0000"

    node_color = "0x7533c1ff"

    def on_load(self, group_node, namespace, context):
        # try to place it under Viewer1
        if not self.connect_active_viewer(group_node):
            nuke.delete(group_node)
            return