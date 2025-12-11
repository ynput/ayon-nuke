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
    product_base_type = "gizmo"
    icon = "file-archive-o"
    default_variants = ["ViewerInput", "Lut", "Effect"]

    # plugin attributes
    node_color = "0x7533c1ff"
    node_class_name = "Group"

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
                created_node = nuke.collapseToGroup()

            created_node["tile_color"].setValue(
                int(self.node_color, 16))

            created_node["name"].setValue(node_name)

            return created_node
