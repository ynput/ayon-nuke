from nukescripts import autoBackdrop

from ayon_nuke.api import (
    NukeCreator,
    maintained_selection,
    select_nodes
)


class CreateBackdrop(NukeCreator):
    """Add Publishable Backdrop"""

    settings_category = "nuke"

    identifier = "create_backdrop"
    label = "Nukenodes (backdrop)"
    product_type = "nukenodes"
    icon = "file-archive-o"
    maintain_selection = True

    # plugin attributes
    node_color = "0xdfea5dff"

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
            if len(node_selection) >= 1:
                select_nodes(node_selection)

            created_node = autoBackdrop()
            created_node["name"].setValue(node_name)
            created_node["tile_color"].setValue(int(self.node_color, 16))
            created_node["note_font_size"].setValue(24)
            created_node["label"].setValue("[{}]".format(node_name))

            return created_node
