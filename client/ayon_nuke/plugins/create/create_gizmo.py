import nuke
from ayon_nuke.api import (
    NukeCreator,
    NukeCreatorError,
    maintained_selection
)


class CreateGizmo(NukeCreator):
    """Add Publishable Group as gizmo"""

    settings_category = "nuke"

    identifier = "create_gizmo"
    label = "Gizmo (group)"
    product_type = "gizmo"
    icon = "file-archive-o"
    default_variants = ["ViewerInput", "Lut", "Effect"]

    # plugin attributes
    node_color = "0x7533c1ff"

    def create_instance_node(
        self,
        node_name,
        knobs=None,
        parent=None,
        node_type=None
    ):
        with maintained_selection():
            if self.selected_node:
                created_node = self.selected_node
            else:
                created_node = nuke.collapseToGroup()

            created_node["tile_color"].setValue(
                int(self.node_color, 16))

            created_node["name"].setValue(node_name)

            return created_node

    def _set_selected_nodes(self, pre_create_data):
        """ Ensure provided selection is valid.

        Args:
            pre_create_data (dict): The pre-create data.

        Raises:
            NukeCreatorError. When provided selection is invalid.
        """
        super()._set_selected_nodes(pre_create_data)

        if len(self.selected_nodes) > 1:
            raise NukeCreatorError("Creator error: Select only one 'Group' node")

        elif not self.selected_nodes:
            self.selected_node = None

        else:
            self.selected_node, = self.selected_nodes
            if self.selected_node.Class() != "Group":
                raise NukeCreatorError("Creator error: Select one 'Group' node type")
