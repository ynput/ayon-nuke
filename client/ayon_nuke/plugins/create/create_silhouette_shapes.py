from ayon_nuke.api import (
    NukeCreator,
    NukeCreatorError,
    maintained_selection
)
import nuke


class CreateSilhouetteShapes(NukeCreator):
    """Add Publishable Silhouette Shapes"""

    settings_category = "nuke"

    identifier = "create_shapes"
    label = "Silhouette Shapes"
    product_base_type = "matteshapes"
    product_type = product_base_type
    icon = "code-fork"
    description = "Create .fxs shapes export for Silhouette"

    # plugin attributes
    node_color = "0xff9100ff"
    node_class_name = {"Roto", "RotoPaint"}

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
            NukeCreatorError:
                When multiple Camera nodes are part of the selection.

        """
        with maintained_selection():
            if node_selection:
                if (
                    len(node_selection) > 1
                    and node_selection[0].Class() in self.node_class_name
                ):
                    raise NukeCreatorError(
                        "Creator error: Select only one "
                        f"nodes belonging to {self.node_class_name}"
                    )

                created_node = node_selection[0]

            else:
                created_node = nuke.createNode("Roto")

            created_node["tile_color"].setValue(
                int(self.node_color, 16))

            created_node.setName(node_name)

            return created_node
