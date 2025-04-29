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
    node_class_name = "Camera3"

    def create_instance_node(
        self,
        node_name,
        knobs=None,
        parent=None,
        node_type=None,
        node_selection=None,
    ):
        """Create node representing instance.

        Arguments:
            node_name (str): Name of the new node.
            knobs (OrderedDict): node knobs name and values
            parent (str): Name of the parent node.
            node_type (str, optional): Nuke node Class.
            node_selection (Optional[list[nuke.Node]]): The node selection.

        Returns:
            nuke.Node: Newly created instance node.

        Raises:
            NukeCreatorError. When multiple Camera nodes are part of the selection.

        """
        with maintained_selection():
            if node_selection:
                if len(node_selection) > 1:
                    raise NukeCreatorError(
                        "Creator error: Select only one "
                        f"{self.node_class_name} node"
                    )

                created_node = node_selection[0]

            else:
                created_node = create_camera_node_by_version()

            created_node["tile_color"].setValue(
                int(self.node_color, 16))

            created_node["name"].setValue(node_name)

            return created_node
