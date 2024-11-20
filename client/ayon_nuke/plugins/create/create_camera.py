import nuke
from ayon_nuke.api import (
    NukeCreator,
    NukeCreatorError,
    maintained_selection
)
from ayon_nuke.api.lib import (
    create_camera_node_by_version
)


class CreateCamera(NukeCreator):
    """Add Publishable Camera"""

    settings_category = "nuke"

    identifier = "create_camera"
    label = "Camera (3d)"
    product_type = "camera"
    icon = "camera"

    # plugin attributes
    node_color = "0xff9100ff"

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
                created_node = create_camera_node_by_version()

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
            raise NukeCreatorError("Creator error: Select only one 'Camera' node")

        elif not self.selected_nodes:
            self.selected_node = None

        else:
            self.selected_node, = self.selected_nodes
            if self.selected_node.Class() != "Camera3":
                raise NukeCreatorError("Creator error: Select one 'Camera3' node type")