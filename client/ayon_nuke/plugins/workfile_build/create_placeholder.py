from __future__ import annotations
import nuke

from ayon_core.pipeline.workfile.workfile_template_builder import (
    CreatePlaceholderItem,
    PlaceholderCreateMixin,
)
from ayon_nuke.api.lib import (
    find_free_space_to_paste_nodes,
    get_extreme_positions,
    get_group_io_nodes,
    imprint,
    refresh_nodes,
    reset_selection,
    get_names_from_nodes,
)
from ayon_nuke.api.workfile_template_builder import (
    NukePlaceholderPlugin
)


class NukePlaceholderCreatePlugin(
    NukePlaceholderPlugin, PlaceholderCreateMixin
):
    identifier = "nuke.create"
    label = "Nuke create"

    item_class = CreatePlaceholderItem

    def _parse_placeholder_node_data(self, node):
        placeholder_data = super()._parse_placeholder_node_data(node)

        node_knobs = node.knobs()
        nb_children = 0
        if "nb_children" in node_knobs:
            nb_children = int(node_knobs["nb_children"].getValue())
        placeholder_data["nb_children"] = nb_children

        siblings = []
        if "siblings" in node_knobs:
            siblings = node_knobs["siblings"].values()
        placeholder_data["siblings"] = siblings

        node_full_name = node.fullName()
        placeholder_data["group_name"] = node_full_name.rpartition(".")[0]
        placeholder_data["last_loaded"] = []
        placeholder_data["delete"] = False
        return placeholder_data

    def _before_instance_create(self, placeholder):
        placeholder.data["nodes_init"] = nuke.allNodes()

    def populate_placeholder(self, placeholder):
        self.populate_create_placeholder(placeholder)

    def repopulate_placeholder(self, placeholder):
        self.populate_create_placeholder(placeholder)

    def get_placeholder_options(self, options=None):
        return self.get_create_plugin_options(options)

    def post_placeholder_process(self, placeholder, failed):
        """Cleanup placeholder after load of its corresponding representations.

        Args:
            placeholder (PlaceholderItem): Item which was just used to load
                representation.
            failed (bool): Loading of representation failed.
        """
        # deselect all selected nodes
        placeholder_node = nuke.toNode(placeholder.scene_identifier)

        # getting the latest nodes added
        nodes_init = placeholder.data["nodes_init"]
        nodes_created = list(set(nuke.allNodes()) - set(nodes_init))
        self.log.debug("Created nodes: {}".format(nodes_created))
        if not nodes_created:
            return

        placeholder.data["delete"] = True

        nodes_created = self._move_to_placeholder_group(
            placeholder, nodes_created
        )
        placeholder.data["last_created"] = nodes_created
        refresh_nodes(nodes_created)

        # positioning of the created nodes
        min_x, min_y, _, _ = get_extreme_positions(nodes_created)
        for node in nodes_created:
            xpos = (node.xpos() - min_x) + placeholder_node.xpos()
            ypos = (node.ypos() - min_y) + placeholder_node.ypos()
            node.setXYpos(xpos, ypos)
        refresh_nodes(nodes_created)

        # fix the problem of z_order for backdrops
        self._fix_z_order(placeholder)

        if placeholder.data.get("keep_placeholder"):
            self._imprint_siblings(placeholder)

        if placeholder.data["nb_children"] == 0:
            # update nodes positions and dimensions and set inputs and
            # outputs of created nodes
            if placeholder.data.get("keep_placeholder"):
                self._update_nodes(placeholder, nuke.allNodes(), nodes_created)

            self._set_created_connections(placeholder)

        else:
            # the created nodes will be placed in a free space

            xpointer, ypointer = find_free_space_to_paste_nodes(
                nodes_created, direction="bottom", offset=200
            )
            node = nuke.createNode("NoOp")
            reset_selection()
            nuke.delete(node)
            for node in nodes_created:
                xpos = (node.xpos() - min_x) + xpointer
                ypos = (node.ypos() - min_y) + ypointer
                node.setXYpos(xpos, ypos)

        placeholder.data["nb_children"] += 1
        reset_selection()

        # go back to root group
        nuke.root().begin()

    def _fix_z_order(self, placeholder):
        """Fix the problem of z_order when a backdrop is create."""

        nodes_created = placeholder.data["last_created"]
        created_backdrops = []
        bd_orders = set()
        for node in nodes_created:
            if isinstance(node, nuke.BackdropNode):
                created_backdrops.append(node)
                bd_orders.add(node.knob("z_order").getValue())

        if not bd_orders:
            return

        sib_orders = set()
        for node_name in placeholder.data["siblings"]:
            node = nuke.toNode(node_name)
            if isinstance(node, nuke.BackdropNode):
                sib_orders.add(node.knob("z_order").getValue())

        if not sib_orders:
            return

        min_order = min(bd_orders)
        max_order = max(sib_orders)
        for backdrop_node in created_backdrops:
            z_order = backdrop_node.knob("z_order").getValue()
            backdrop_node.knob("z_order").setValue(
                z_order + max_order - min_order + 1)

    def _imprint_siblings(self, placeholder):
        """
        - add siblings names to placeholder attributes (nodes created with it)
        - add Id to the attributes of all the other nodes
        """

        created_nodes = placeholder.data["last_created"]
        created_nodes_set = set(created_nodes)

        for node in created_nodes:
            node_knobs = node.knobs()

            if (
                "is_placeholder" not in node_knobs
                or (
                    "is_placeholder" in node_knobs
                    and node.knob("is_placeholder").value()
                )
            ):
                siblings = list(created_nodes_set - {node})
                siblings_name = get_names_from_nodes(siblings)
                siblings = {"siblings": siblings_name}
                imprint(node, siblings)

    def _set_created_connections(self, placeholder):
        """
        set inputs and outputs of created nodes"""

        placeholder_node = nuke.toNode(placeholder.scene_identifier)
        input_node, output_node = get_group_io_nodes(
            placeholder.data["last_created"]
        )
        for node in placeholder_node.dependent():
            for idx in range(node.inputs()):
                if node.input(idx) == placeholder_node and output_node:
                    node.setInput(idx, output_node)

        for node in placeholder_node.dependencies():
            for idx in range(placeholder_node.inputs()):
                if placeholder_node.input(idx) == node and input_node:
                    input_node.setInput(0, node)
